from flask import Flask, render_template, request, jsonify, send_from_directory, make_response, send_file
from openai import OpenAI
import json
import os
import pdfkit
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import markdown
import io

app = Flask(__name__)

# Initialize OpenAI client with base URL for Azure OpenAI
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),  # Read from environment variable
    base_url="https://api.openai.com/v1"  # Optional, default already points here
)

# Load assessment questions
with open('backend/questions.json', 'r') as f:
    ASSESSMENT_QUESTIONS = json.load(f)

# Configure wkhtmltopdf path
if os.name == 'nt':  # Windows
    WKHTMLTOPDF_PATH = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    if not os.path.exists(WKHTMLTOPDF_PATH):
        # Try alternative paths
        alternative_paths = [
            r'C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe',
            r'wkhtmltopdf'  # If it's in system PATH
        ]
        for path in alternative_paths:
            if os.path.exists(path):
                WKHTMLTOPDF_PATH = path
                break
else:  # Linux/Unix/MacOS
    WKHTMLTOPDF_PATH = '/usr/local/bin/wkhtmltopdf'

# Configure pdfkit
config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/assessment')
def assessment():
    return render_template('assessment.html')

@app.route('/static/data/<path:filename>')
def serve_data(filename):
    return send_from_directory('static/data', filename)

@app.route('/api/generate-recommendations', methods=['POST'])
def generate_recommendations():
    data = request.json
    assessment_results = data.get('assessment_results', [])
    
    # Group results by category
    results_by_category = {}
    for result in assessment_results:
        if result['category'] not in results_by_category:
            results_by_category[result['category']] = []
        results_by_category[result['category']].append(result)
    
    # Prepare the prompt for OpenAI
    prompt = """Analyze the following assessment results for a university program and generate specific recommendations.
    The assessment uses a 1-4 scale where 1-2 indicates weak performance, 3 indicates moderate performance, and 4 indicates strong performance.

    Assessment Results by Category:
    {}

    Based on these results, provide recommendations, evidence requirements, and KPIs.
    Focus particularly on areas rated 3 or lower that need improvement.""".format(
        json.dumps(results_by_category, indent=2)
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert in university program assessment and accreditation.
                    You must respond with a valid JSON object containing exactly these keys:
                    - recommendations: array of objects with 'category' and 'items' keys
                    - evidence: array of strings
                    - kpis: array of strings"""
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000,
            response_format={"type": "json_object"}  # Force JSON response
        )
        
        # Parse and validate the response
        try:
            recommendations = json.loads(response.choices[0].message.content)
            
            # Validate response structure
            if not isinstance(recommendations, dict):
                raise ValueError("Response is not a dictionary")
            
            required_keys = ['recommendations', 'evidence', 'kpis']
            if not all(key in recommendations for key in required_keys):
                raise ValueError(f"Missing required keys. Expected: {required_keys}")
            
            if not isinstance(recommendations['recommendations'], list):
                raise ValueError("'recommendations' must be an array")
            
            if not isinstance(recommendations['evidence'], list):
                raise ValueError("'evidence' must be an array")
            
            if not isinstance(recommendations['kpis'], list):
                raise ValueError("'kpis' must be an array")
            
            # Validate recommendations structure
            for rec in recommendations['recommendations']:
                if not isinstance(rec, dict) or 'category' not in rec or 'items' not in rec:
                    raise ValueError("Invalid recommendation format")
                if not isinstance(rec['items'], list):
                    raise ValueError("Recommendation items must be an array")
            
            return jsonify(recommendations)
            
        except json.JSONDecodeError as e:
            app.logger.error(f"Failed to parse OpenAI response as JSON: {str(e)}")
            app.logger.error(f"Response content: {response.choices[0].message.content}")
            return jsonify({"error": "Failed to generate valid recommendations"}), 500
            
        except ValueError as e:
            app.logger.error(f"Invalid response format: {str(e)}")
            return jsonify({"error": "Invalid recommendations format"}), 500
            
    except Exception as e:
        app.logger.error(f"Error generating recommendations: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate-report', methods=['POST'])
def generate_report():
    try:
        data = request.json
        institution_info = data.get('institution_info', {})
        assessment_results = data.get('assessment_results', [])
        recommendations = data.get('recommendations', {})

        # Prepare the prompt for OpenAI
        prompt = f"""
        Generate a comprehensive program assessment report with the following structure:

        First, start with a summary of the program information:

        Section A: GENERAL INFORMATION
        - Institution Name: {institution_info.get('institutionName', '-')}
        - Program Name: {institution_info.get('programName', '-')}
        - Year Established: {institution_info.get('yearEstablished', '-')}
        - Total Number of Graduates: {institution_info.get('totalGraduates', '-')}
        - First Graduating Batch: {institution_info.get('firstGraduatingBatch', '-')}
        - Current Number of Students: {institution_info.get('currentStudents', '-')}
        - Number of Faculty Members: {institution_info.get('facultyMembers', '-')}
        - Program Tracks: {institution_info.get('programTracks', '-')}
        - Total Credit Hours: {institution_info.get('creditHours', '-')}

        Then, analyze the following assessment results for each standard and generate specific recommendations.
        The assessment uses a 4-point scale where:
        1 = Non-Compliant
        2 = Minimal Compliance
        3 = Substantial Compliance
        4 = Full Compliance

        Assessment Results by Category:
        {json.dumps(assessment_results, indent=2)}

        Recommendations:
        {json.dumps(recommendations, indent=2)}

        For each standard, provide a detailed analysis in a single table with four columns:
        | Strengths | Weaknesses | Recommendations | Key Performance Indicators (KPIs) |

        Important formatting rules:
        1. Each cell should contain bullet points starting with "• "
        2. For every weakness point identified, there MUST be a corresponding recommendation that directly addresses it
        3. All KPIs must be specific, measurable, and quantifiable with clear metrics
        4. Each standard's table should be presented as a single row with four columns
        5. Ensure recommendations are actionable and specific

        Required KPIs for each standard (in addition to other relevant KPIs):

        Section A: PROGRAM MANAGEMENT and QUALITY ASSURANCE: 
        • Percentage of achieved program operational plan objectives (Target: %)
        • Program satisfaction rate from stakeholders (Target: %)
        • Number of quality improvement initiatives implemented per year (Target: #)

        Standard 2: TEACHING and LEARNING: 
        • Students' overall satisfaction with learning experience (Target: %)
        • Course satisfaction rate (Target: %)
        • Employer satisfaction rate with graduates' performance (Target: %)
        • Course completion rate (Target: %)

        Standard 3: STUDENTS: 
        • Student-to-faculty ratio (Target: #:1)
        • Average time to graduation (Target: # years)
        • Student retention rate (Target: %)
        • Graduate employment rate within 6 months (Target: %)

        Standard 4: FACULTY: 
        • Percentage of faculty with terminal degrees (Target: %)
        • Faculty retention rate (Target: %)
        • Faculty research publications per year (Target: # per faculty)
        • Faculty professional development participation rate (Target: %)

        Standard 5: LEARNING RESOURCES, FACILITIES, and EQUIPMENT: 
        • Student satisfaction with learning resources (Target: %)
        • Faculty satisfaction with teaching facilities (Target: %)
        • Resource utilization rate (Target: %)
        • Annual technology refresh rate (Target: %)

        After the analysis of each standard, provide a concise executive summary that includes:
        1. One key strength for each standard (exactly one, the most significant)
        2. The main weaknesses that require immediate attention (prioritized)
        3. The corresponding recommendations for these critical weaknesses
        4. An overall assessment of the program's compliance level

        Format the report in Markdown with proper headings and tables.
        Make all tables full-width and ensure consistent formatting throughout.
        Use bullet points for all lists within table cells.
        If any data point is missing, use a '-' as a placeholder.
        """

        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert in program assessment and accreditation. Generate a detailed, professional report with specific recommendations and KPIs for each standard. Format all content in tables as bullet points for better readability."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )

        report = response.choices[0].message.content

        return jsonify({"report": report})

    except Exception as e:
        app.logger.error(f"Error generating report: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate-pdf', methods=['POST'])
def generate_pdf():
    try:
        data = request.json
        html_content = data.get('html_content')
        institution_info = data.get('institution_info', {})

        # Create a configuration for wkhtmltopdf
        try:
            config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
        except Exception as e:
            app.logger.error(f"Error configuring wkhtmltopdf: {str(e)}")
            return jsonify({
                "error": "PDF generation failed. Please make sure wkhtmltopdf is installed. Download from: https://wkhtmltopdf.org/downloads.html"
            }), 500
        
        # Create a complete HTML document with styling
        complete_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
                body {{
                    font-family: 'Inter', sans-serif;
                    line-height: 1.6;
                    color: #2c3e50;
                    margin: 1.5cm;
                    max-width: 1200px;
                    margin-left: auto;
                    margin-right: auto;
                }}
                h1 {{
                    color: #2c3e50;
                    border-bottom: 3px solid #2874a6;
                    padding-bottom: 10px;
                }}
                h2 {{
                    color: #2c3e50;
                    margin-top: 20px;
                    border-bottom: 1px solid #2874a6;
                    padding-bottom: 5px;
                }}
                h3 {{
                    color: #2874a6;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                    page-break-inside: auto;
                }}
                tr {{
                    page-break-inside: avoid;
                    page-break-after: auto;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 12px;
                    text-align: left;
                    vertical-align: top;
                }}
                th {{
                    background-color: #2874a6;
                    color: white;
                    font-weight: 600;
                }}
                tr:nth-child(even) {{
                    background-color: #f5f5f5;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .footer {{
                    margin-top: 50px;
                    text-align: center;
                    font-size: 0.9em;
                    color: #7f8c8d;
                    border-top: 1px solid #ddd;
                    padding-top: 20px;
                }}
                .executive-summary {{
                    background-color: #f8f9fa;
                    padding: 15px;
                    border-left: 4px solid #2874a6;
                    margin: 20px 0;
                }}
                ul, ol {{
                    padding-left: 20px;
                    margin: 0;
                }}
                li {{
                    margin-bottom: 5px;
                }}
                td ul {{
                    list-style-type: none;
                    padding-left: 0;
                }}
                td ul li:before {{
                    content: "•";
                    color: #2874a6;
                    display: inline-block;
                    width: 1em;
                    margin-left: -1em;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Program Assessment Report</h1>
                <h2>{institution_info.get('programName', '')}</h2>
                <h3>{institution_info.get('institutionName', '')}</h3>
                <p>Generated on {datetime.now().strftime('%B %d, %Y')}</p>
            </div>
            
            {html_content}
            
            <div class="footer">
                <p>Generated by AccreditAI</p>
                <p>Page <span class="page"></span> of <span class="topage"></span></p>
            </div>
        </body>
        </html>
        """

        try:
            # Generate PDF with more detailed options
            pdf = pdfkit.from_string(complete_html, False, options={
                'page-size': 'A4',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
                'encoding': 'UTF-8',
                'enable-local-file-access': True,
                'footer-right': '[page] of [topage]',
                'footer-font-size': '9',
                'footer-line': True,
                'footer-spacing': '5'
            }, configuration=config)
        except Exception as e:
            app.logger.error(f"Error in PDF generation: {str(e)}")
            return jsonify({
                "error": "Failed to generate PDF. Please ensure wkhtmltopdf is properly installed."
            }), 500

        # Create response
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=AccreditAI_{institution_info.get("programName", "Program").replace(" ", "_")}_Assessment_Report.pdf'
        
        return response

    except Exception as e:
        app.logger.error(f"Error in generate_pdf route: {str(e)}")
        return jsonify({
            "error": "An unexpected error occurred while generating the PDF. Please try again or contact support."
        }), 500

@app.route('/api/share-report', methods=['POST'])
def share_report():
    try:
        data = request.json
        institution_info = data.get('institution_info', {})
        assessment_results = data.get('assessment_results', [])
        recommendations = data.get('recommendations', {})
        report = data.get('report', '')
        email = data.get('email')

        # Generate HTML content from the Markdown report
        html_report = markdown.markdown(report, extensions=['tables'])

        # Generate PDF
        complete_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
                body {{
                    font-family: 'Inter', sans-serif;
                    line-height: 1.6;
                    color: #2c3e50;
                    margin: 2cm;
                }}
                h1 {{
                    color: #2c3e50;
                    border-bottom: 3px solid #2874a6;
                    padding-bottom: 10px;
                }}
                h2 {{
                    color: #2c3e50;
                    margin-top: 20px;
                    border-bottom: 1px solid #2874a6;
                    padding-bottom: 5px;
                }}
                h3 {{
                    color: #2874a6;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                    page-break-inside: auto;
                }}
                tr {{
                    page-break-inside: avoid;
                    page-break-after: auto;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 12px;
                    text-align: left;
                }}
                th {{
                    background-color: #2874a6;
                    color: white;
                    font-weight: 600;
                }}
                tr:nth-child(even) {{
                    background-color: #f5f5f5;
                }}
                .header {{
                    margin-bottom: 30px;
                }}
                .footer {{
                    margin-top: 50px;
                    text-align: center;
                    font-size: 0.9em;
                    color: #7f8c8d;
                    border-top: 1px solid #ddd;
                    padding-top: 20px;
                }}
                .executive-summary {{
                    background-color: #f8f9fa;
                    padding: 15px;
                    border-left: 4px solid #2874a6;
                    margin: 20px 0;
                }}
                ul, ol {{
                    padding-left: 20px;
                }}
                li {{
                    margin-bottom: 5px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Program Assessment Report</h1>
                <p>
                    <strong>Institution:</strong> {institution_info.get('institutionName', '')}<br>
                    <strong>Program:</strong> {institution_info.get('programName', '')}<br>
                    <strong>Generated on:</strong> {datetime.now().strftime('%B %d, %Y')}
                </p>
            </div>
            
            {html_report}
            
            <div class="footer">
                <p>Generated by AccreditAI | Developed by Prof. Yasser Mansour & Ahmed Yasser</p>
                <p>Prince Sultan University</p>
            </div>
        </body>
        </html>
        """

        # Configure PDF options
        config = None
        if os.name == 'nt':  # Windows
            config = pdfkit.configuration(wkhtmltopdf='C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe')

        pdf = pdfkit.from_string(complete_html, False, options={
            'page-size': 'A4',
            'margin-top': '0.75in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
            'encoding': 'UTF-8',
            'enable-local-file-access': True
        }, configuration=config)

        # Email configuration
        sender_email = "accreditai.system@gmail.com"  # You'll need to set up this email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = email
        msg['Subject'] = f"AccreditAI Assessment Report - {institution_info.get('programName', 'Program')} - {datetime.now().strftime('%Y-%m-%d')}"

        # Add body
        body = f"""
        Program Assessment Report
        
        Institution: {institution_info.get('institutionName', '')}
        Program: {institution_info.get('programName', '')}
        Generated on: {datetime.now().strftime('%B %d, %Y')}
        
        This report was shared with the AccreditAI development team for analysis and improvement purposes.
        """
        msg.attach(MIMEText(body, 'plain'))

        # Add PDF attachment
        pdf_attachment = MIMEApplication(pdf, _subtype='pdf')
        pdf_attachment.add_header('Content-Disposition', 'attachment', 
                                filename=f"AccreditAI_{institution_info.get('programName', 'Program').replace(' ', '_')}_Assessment_Report.pdf")
        msg.attach(pdf_attachment)

        # Send email
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, os.getenv('EMAIL_PASSWORD'))
            server.send_message(msg)

        return jsonify({"message": "Report shared successfully"})

    except Exception as e:
        app.logger.error(f"Error sharing report: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/ask')
def ask_page():
    return render_template('ask.html')

@app.route('/api/ask', methods=['POST'])
def ask_ai():
    try:
        data = request.json
        question = data.get('question', '')

        # Prepare the prompt for OpenAI
        prompt = f"""You are an accreditation consultant specializing in university program assessment.

                    Answer the following question about accreditation:

                    Question: {question}

                    Instructions:
                    - Always give a clear, direct, and professional answer first. 
                    - If the question is factual (e.g., "which body," "how long," "what is"), 
                    provide only the factual answer with relevant details or examples. 
                    Do NOT add recommendations unless explicitly asked. 
                    - If the question is advisory (e.g., "how should we," "what steps," "ways to improve"), 
                    then provide practical, actionable recommendations aligned with accreditation standards.
                    - When relevant, mention examples of accreditation bodies (ABET, AACSB, NCAAA, etc.) 
                    or best practices, but keep the focus on directly answering the question.
                    - Avoid repeating definitions or explaining accreditation unless the question explicitly requests it.
                    - Keep responses concise, professional, and to the point. """

        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert in university program accreditation and assessment. Provide clear, professional advice."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )

        return jsonify({"response": response.choices[0].message.content})

    except Exception as e:
        app.logger.error(f"Error in AI response: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 