from flask import Flask, render_template, request, jsonify, send_from_directory, make_response, send_file
from openai import OpenAI
import json
import os
from datetime import datetime
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
            max_tokens=1500,
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
            max_tokens=2000
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

        # Create a beautiful HTML report instead of PDF
        complete_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Program Assessment Report - {institution_info.get('programName', 'Program')}</title>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: 'Inter', Arial, Helvetica, sans-serif;
                    line-height: 1.6;
                    color: #2c3e50;
                    background-color: #f8f9fa;
                    padding: 2rem;
                }}
                
                .report-container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                
                .report-header {{
                    background: linear-gradient(135deg, #2874a6 0%, #3498db 100%);
                    color: white;
                    padding: 3rem 2rem;
                    text-align: center;
                }}
                
                .report-header h1 {{
                    font-size: 2.5rem;
                    font-weight: 700;
                    margin-bottom: 1rem;
                }}
                
                .report-header h2 {{
                    font-size: 1.5rem;
                    font-weight: 500;
                    margin-bottom: 0.5rem;
                    opacity: 0.9;
                }}
                
                .report-header p {{
                    font-size: 1.1rem;
                    opacity: 0.8;
                }}
                
                .report-content {{
                    padding: 3rem 2rem;
                }}
                
                .report-content h1 {{
                    color: #2874a6;
                    font-size: 2rem;
                    margin-bottom: 1.5rem;
                    padding-bottom: 1rem;
                    border-bottom: 3px solid #3498db;
                }}
                
                .report-content h2 {{
                    color: #2874a6;
                    font-size: 1.5rem;
                    margin: 2rem 0 1rem;
                    padding-bottom: 0.5rem;
                    border-bottom: 1px solid #e9ecef;
                }}
                
                .report-content h3 {{
                    color: #2c3e50;
                    font-size: 1.2rem;
                    margin: 1.5rem 0 0.75rem;
                }}
                
                .report-content p {{
                    margin-bottom: 1rem;
                    font-size: 1.1rem;
                }}
                
                .report-content table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 1.5rem 0;
                    background: white;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                
                .report-content th {{
                    background: #2874a6;
                    color: white;
                    padding: 1rem;
                    text-align: left;
                    font-weight: 600;
                    font-size: 1rem;
                }}
                
                .report-content td {{
                    padding: 1rem;
                    border-bottom: 1px solid #e9ecef;
                    vertical-align: top;
                }}
                
                .report-content tr:nth-child(even) {{
                    background-color: #f8f9fa;
                }}
                
                .report-content tr:hover {{
                    background-color: #e3f2fd;
                }}
                
                .report-content ul, .report-content ol {{
                    margin: 1rem 0;
                    padding-left: 2rem;
                }}
                
                .report-content li {{
                    margin-bottom: 0.5rem;
                    font-size: 1.1rem;
                }}
                
                .report-content blockquote {{
                    border-left: 4px solid #3498db;
                    padding-left: 1.5rem;
                    margin: 1.5rem 0;
                    color: #6c757d;
                    font-style: italic;
                    background: #f8f9fa;
                    padding: 1rem;
                    border-radius: 0 8px 8px 0;
                }}
                
                .report-footer {{
                    background: #f8f9fa;
                    padding: 2rem;
                    text-align: center;
                    border-top: 1px solid #e9ecef;
                }}
                
                .report-footer p {{
                    color: #6c757d;
                    margin-bottom: 0.5rem;
                }}
                
                .download-section {{
                    text-align: center;
                    margin: 2rem 0;
                    padding: 2rem;
                    background: #f8f9fa;
                    border-radius: 8px;
                }}
                
                .download-btn {{
                    display: inline-block;
                    background: #2874a6;
                    color: white;
                    padding: 1rem 2rem;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: 600;
                    transition: all 0.3s ease;
                    margin: 0.5rem;
                    border: none;
                    cursor: pointer;
                    font-size: 1rem;
                }}
                
                .download-btn:hover {{
                    background: #1a5276;
                    transform: translateY(-2px);
                    box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                }}
                
                .print-btn {{
                    background: #28a745;
                }}
                
                .print-btn:hover {{
                    background: #1e7e34;
                }}
                
                @media print {{
                    body {{
                        background: white;
                        padding: 0;
                    }}
                    .report-container {{
                        box-shadow: none;
                        border-radius: 0;
                    }}
                    .download-section {{
                        display: none;
                    }}
                }}
                
                @media (max-width: 768px) {{
                    body {{
                        padding: 1rem;
                    }}
                    .report-header {{
                        padding: 2rem 1rem;
                    }}
                    .report-header h1 {{
                        font-size: 2rem;
                    }}
                    .report-content {{
                        padding: 2rem 1rem;
                    }}
                    .report-content table {{
                        font-size: 0.9rem;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="report-container">
                <div class="report-header">
                    <h1>Program Assessment Report</h1>
                    <h2>{institution_info.get('programName', 'Program Name')}</h2>
                    <p>{institution_info.get('institutionName', 'Institution Name')}</p>
                    <p>Generated on {datetime.now().strftime('%B %d, %Y')}</p>
                </div>
                
                <div class="report-content">
                    {html_content}
                </div>
                
                <div class="download-section">
                    <button class="download-btn" onclick="window.print()">
                        <i class="fas fa-print"></i> Print Report
                    </button>
                    <button class="download-btn print-btn" onclick="downloadAsPDF()">
                        <i class="fas fa-file-pdf"></i> Save as PDF
                    </button>
                </div>
                
                <div class="report-footer">
                    <p><strong>Generated by AccreditAI</strong></p>
                    <p>Developed by Prof. Yasser Mansour & Ahmed Yasser</p>
                    <p>Prince Sultan University</p>
                </div>
            </div>
            
            <script>
                function downloadAsPDF() {{
                    // Simple PDF generation using browser's print to PDF
                    window.print();
                }}
                
                // Add smooth scrolling
                document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
                    anchor.addEventListener('click', function (e) {{
                        e.preventDefault();
                        document.querySelector(this.getAttribute('href')).scrollIntoView({{
                            behavior: 'smooth'
                        }});
                    }});
                }});
            </script>
        </body>
        </html>
        """

        return jsonify({"html_report": complete_html})

    except Exception as e:
        app.logger.error(f"Error generating HTML report: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/share-report', methods=['POST'])
def share_report():
    try:
        data = request.json
        institution_info = data.get('institution_info', {})
        assessment_results = data.get('assessment_results', [])
        recommendations = data.get('recommendations', {})
        report = data.get('report', '')

        # Generate HTML content from the Markdown report
        html_report = markdown.markdown(report, extensions=['tables'])

        # Create a beautiful HTML report page
        complete_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Program Assessment Report - {institution_info.get('programName', 'Program')}</title>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: 'Inter', Arial, Helvetica, sans-serif;
                    line-height: 1.6;
                    color: #2c3e50;
                    background-color: #f8f9fa;
                    padding: 2rem;
                }}
                
                .report-container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                
                .report-header {{
                    background: linear-gradient(135deg, #2874a6 0%, #3498db 100%);
                    color: white;
                    padding: 3rem 2rem;
                    text-align: center;
                }}
                
                .report-header h1 {{
                    font-size: 2.5rem;
                    font-weight: 700;
                    margin-bottom: 1rem;
                }}
                
                .report-header h2 {{
                    font-size: 1.5rem;
                    font-weight: 500;
                    margin-bottom: 0.5rem;
                    opacity: 0.9;
                }}
                
                .report-header p {{
                    font-size: 1.1rem;
                    opacity: 0.8;
                }}
                
                .report-content {{
                    padding: 3rem 2rem;
                }}
                
                .report-content h1 {{
                    color: #2874a6;
                    font-size: 2rem;
                    margin-bottom: 1.5rem;
                    padding-bottom: 1rem;
                    border-bottom: 3px solid #3498db;
                }}
                
                .report-content h2 {{
                    color: #2874a6;
                    font-size: 1.5rem;
                    margin: 2rem 0 1rem;
                    padding-bottom: 0.5rem;
                    border-bottom: 1px solid #e9ecef;
                }}
                
                .report-content h3 {{
                    color: #2c3e50;
                    font-size: 1.2rem;
                    margin: 1.5rem 0 0.75rem;
                }}
                
                .report-content p {{
                    margin-bottom: 1rem;
                    font-size: 1.1rem;
                }}
                
                .report-content table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 1.5rem 0;
                    background: white;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                
                .report-content th {{
                    background: #2874a6;
                    color: white;
                    padding: 1rem;
                    text-align: left;
                    font-weight: 600;
                    font-size: 1rem;
                }}
                
                .report-content td {{
                    padding: 1rem;
                    border-bottom: 1px solid #e9ecef;
                    vertical-align: top;
                }}
                
                .report-content tr:nth-child(even) {{
                    background-color: #f8f9fa;
                }}
                
                .report-content tr:hover {{
                    background-color: #e3f2fd;
                }}
                
                .report-content ul, .report-content ol {{
                    margin: 1rem 0;
                    padding-left: 2rem;
                }}
                
                .report-content li {{
                    margin-bottom: 0.5rem;
                    font-size: 1.1rem;
                }}
                
                .report-content blockquote {{
                    border-left: 4px solid #3498db;
                    padding-left: 1.5rem;
                    margin: 1.5rem 0;
                    color: #6c757d;
                    font-style: italic;
                    background: #f8f9fa;
                    padding: 1rem;
                    border-radius: 0 8px 8px 0;
                }}
                
                .report-footer {{
                    background: #f8f9fa;
                    padding: 2rem;
                    text-align: center;
                    border-top: 1px solid #e9ecef;
                }}
                
                .report-footer p {{
                    color: #6c757d;
                    margin-bottom: 0.5rem;
                }}
                
                .download-section {{
                    text-align: center;
                    margin: 2rem 0;
                    padding: 2rem;
                    background: #f8f9fa;
                    border-radius: 8px;
                }}
                
                .download-btn {{
                    display: inline-block;
                    background: #2874a6;
                    color: white;
                    padding: 1rem 2rem;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: 600;
                    transition: all 0.3s ease;
                    margin: 0.5rem;
                    border: none;
                    cursor: pointer;
                    font-size: 1rem;
                }}
                
                .download-btn:hover {{
                    background: #1a5276;
                    transform: translateY(-2px);
                    box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                }}
                
                .print-btn {{
                    background: #28a745;
                }}
                
                .print-btn:hover {{
                    background: #1e7e34;
                }}
                
                @media print {{
                    body {{
                        background: white;
                        padding: 0;
                    }}
                    .report-container {{
                        box-shadow: none;
                        border-radius: 0;
                    }}
                    .download-section {{
                        display: none;
                    }}
                }}
                
                @media (max-width: 768px) {{
                    body {{
                        padding: 1rem;
                    }}
                    .report-header {{
                        padding: 2rem 1rem;
                    }}
                    .report-header h1 {{
                        font-size: 2rem;
                    }}
                    .report-content {{
                        padding: 2rem 1rem;
                    }}
                    .report-content table {{
                        font-size: 0.9rem;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="report-container">
                <div class="report-header">
                    <h1>Program Assessment Report</h1>
                    <h2>{institution_info.get('programName', 'Program Name')}</h2>
                    <p>{institution_info.get('institutionName', 'Institution Name')}</p>
                    <p>Generated on {datetime.now().strftime('%B %d, %Y')}</p>
                </div>
                
                <div class="report-content">
                    {html_report}
                </div>
                
                <div class="download-section">
                    <button class="download-btn" onclick="window.print()">
                        <i class="fas fa-print"></i> Print Report
                    </button>
                    <button class="download-btn print-btn" onclick="downloadAsPDF()">
                        <i class="fas fa-file-pdf"></i> Save as PDF
                    </button>
                </div>
                
                <div class="report-footer">
                    <p><strong>Generated by AccreditAI</strong></p>
                    <p>Developed by Prof. Yasser Mansour & Ahmed Yasser</p>
                    <p>Prince Sultan University</p>
                </div>
            </div>
            
            <script>
                function downloadAsPDF() {{
                    // Simple PDF generation using browser's print to PDF
                    window.print();
                }}
                
                // Add smooth scrolling
                document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
                    anchor.addEventListener('click', function (e) {{
                        e.preventDefault();
                        document.querySelector(this.getAttribute('href')).scrollIntoView({{
                            behavior: 'smooth'
                        }});
                    }});
                }});
            </script>
        </body>
        </html>
        """

        return jsonify({"html_report": complete_html})

    except Exception as e:
        app.logger.error(f"Error generating HTML report: {str(e)}")
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