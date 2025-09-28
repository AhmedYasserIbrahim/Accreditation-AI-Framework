// State management
const state = {
    institutionInfo: {},
    currentSection: 'general-info',
    currentQuestionIndex: 0,
    currentQuestions: [],
    questions: null,
    assessmentResults: [],
    recommendations: null,
    report: null
};

// DOM Elements
const chatMessages = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');
const ratingButtons = document.getElementById('ratingButtons');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const navItems = document.querySelectorAll('.nav-item');

// General information fields to collect
const generalInfoFields = [
    { key: 'institutionName', label: 'Institution Name', value: 'Prince Sultan University' },
    { key: 'programName', label: 'Program Name' },
    { key: 'yearEstablished', label: 'Year of Establishment' },
    { key: 'totalGraduates', label: 'Total Number of Graduates' },
    { key: 'firstGraduatingBatch', label: 'First Graduating Batch (Year)' },
    { key: 'currentStudents', label: 'Number of Current Students' },
    { key: 'facultyMembers', label: 'Number of Faculty Members' },
    { key: 'programTracks', label: 'Program Tracks (comma-separated)' },
    { key: 'creditHours', label: 'Total Credit Hours Required for Graduation' }
];

// Add section descriptions
const sectionDescriptions = {
    'general-info': 'Let\'s start by gathering some basic information about your program. This will help provide context for the assessment.',
    'mission-goals': 'This section evaluates how well your program\'s mission and goals align with institutional objectives and industry standards.',
    'program-management-quality-assurance': 'We\'ll assess the effectiveness of your program\'s management structure and quality assurance processes.',
    'teaching-learning': 'This section focuses on teaching methodologies, learning outcomes, and educational effectiveness.',
    'curriculum-assessment': 'We\'ll evaluate your curriculum design, content, and assessment methods.',
    'students-alumni-services': 'This section examines student support services and alumni engagement.',
    'faculty-staff': 'We\'ll assess faculty qualifications, development opportunities, and support systems.',
    'learning-resources-facilities': 'This section evaluates the adequacy of learning resources and facilities.',
    'assessment-continuous-improvement': 'Finally, we\'ll examine your program\'s assessment practices and improvement processes.'
};

// Add rating scale explanation
const ratingScaleExplanation = `
    <div class="rating-legend">
        <strong>Rating Scale Guide:</strong><br>
        1 - Non-Compliant<br>
        2 - Minimal Compliance<br>
        3 - Substantial Compliance<br>
        4 - Full Compliance
    </div>
`;

// Add rating labels
const ratingLabels = {
    1: 'Non-Compliant',
    2: 'Minimal Compliance',
    3: 'Substantial Compliance',
    4: 'Full Compliance'
};

// Map section IDs to category names in the questions.json file
const sectionToCategoryMap = {
    'program-management': 'Section A: PROGRAM MANAGEMENT and QUALITY ASSURANCE',
    'teaching-learning': 'Standard 2: TEACHING and LEARNING',
    'students': 'Standard 3: STUDENTS',
    'faculty': 'Standard 4: FACULTY',
    'resources': 'Standard 5: LEARNING RESOURCES, FACILITIES, and EQUIPMENT'
};

// Event Listeners
sendButton.addEventListener('click', handleSend);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleSend();
});

// Initialize chat
async function initializeChat() {
    try {
        // Load questions
        const response = await fetch('/static/data/questions.json');
        if (!response.ok) {
            throw new Error('Failed to load questions');
        }
        
        state.questions = await response.json();
        
        // Start with welcome message
        addBotMessage('Welcome to the Program Assessment Tool! I\'ll guide you through the assessment process.');
        addBotMessage('Let\'s start by gathering some basic information about your program.');
        
        // Ask first general info question
        askNextGeneralInfoQuestion();
        
    } catch (error) {
        console.error('Error initializing chat:', error);
        addBotMessage('There was an error loading the assessment questions. Please refresh the page or contact support.');
    }
}

// Clear chat messages
function clearMessages() {
    while (chatMessages.firstChild) {
        chatMessages.removeChild(chatMessages.firstChild);
    }
}

// Handle user input submission
function handleSend() {
    const input = userInput.value.trim();
    if (!input) return;

    addUserMessage(input);
    userInput.value = '';

    if (state.currentSection === 'general-info') {
        handleGeneralInfoInput(input);
    }
}

// Add loading state management
function showLoading(message) {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'loading-message';
    loadingDiv.innerHTML = `
        <div class="loading-spinner"></div>
        <p>${message}</p>
    `;
    chatMessages.appendChild(loadingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function hideLoading() {
    const loadingMessage = chatMessages.querySelector('.loading-message');
    if (loadingMessage) {
        loadingMessage.remove();
    }
}

// Enhance the message display with animations
function addBotMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot';
    messageDiv.style.opacity = '0';
    messageDiv.style.transform = 'translateY(20px)';
    messageDiv.innerHTML = message;
    chatMessages.appendChild(messageDiv);
    
    // Trigger animation
    setTimeout(() => {
        messageDiv.style.opacity = '1';
        messageDiv.style.transform = 'translateY(0)';
    }, 100);
    
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addUserMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user';
    messageDiv.style.opacity = '0';
    messageDiv.style.transform = 'translateY(20px)';
    messageDiv.textContent = message;
    chatMessages.appendChild(messageDiv);
    
    // Trigger animation
    setTimeout(() => {
        messageDiv.style.opacity = '1';
        messageDiv.style.transform = 'translateY(0)';
    }, 100);
    
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Handle general information input
function handleGeneralInfoInput(input) {
    const currentField = generalInfoFields[state.currentQuestionIndex];
    state.institutionInfo[currentField.key] = input;
    state.currentQuestionIndex++;

    if (state.currentQuestionIndex < generalInfoFields.length) {
        askNextGeneralInfoQuestion();
    } else {
        startAssessment();
    }

    updateProgress();
    updateNavigation();
}

// Ask the next general information question
function askNextGeneralInfoQuestion() {
    const field = generalInfoFields[state.currentQuestionIndex];
    clearMessages();
    addBotMessage(`Please enter the ${field.label}:`);
}

// Start the assessment section
function startAssessment() {
    state.currentSection = 'program-management';
    state.currentQuestionIndex = 0;
    
    // Find the category that matches the current section
    const category = state.questions.categories.find(
        cat => cat.name === sectionToCategoryMap[state.currentSection]
    );
    
    if (category) {
        state.currentQuestions = category.questions;
        showSectionDescription();
    } else {
        addBotMessage("Error: Could not find questions for this section. Please contact support.");
    }
    
    // Update navigation
    updateNavigation();
}

// Show section description
function showSectionDescription() {
    const currentSection = state.currentSection;
    let description = '';
    
    switch (currentSection) {
        case 'program-management':
            description = 'This section evaluates the program\'s management structure, quality assurance mechanisms, and administrative processes. It assesses how well the program is governed, monitored, and continuously improved.';
            break;
        case 'teaching-learning':
            description = 'This section examines the program\'s teaching methodologies, learning outcomes, curriculum design, and assessment strategies. It evaluates how effectively the program delivers educational content and ensures student learning.';
            break;
        case 'students':
            description = 'This section focuses on student services, support mechanisms, admission processes, and overall student experience. It assesses how well the program meets student needs and supports their academic journey.';
            break;
        case 'faculty':
            description = 'This section evaluates faculty qualifications, development opportunities, research activities, and performance assessment. It examines how effectively faculty members contribute to program quality and student learning.';
            break;
        case 'resources':
            description = 'This section assesses the learning resources, facilities, equipment, and technological infrastructure available to support the program. It evaluates the adequacy and effectiveness of these resources for teaching and learning.';
            break;
        case 'research':
            description = 'This section examines the program\'s research activities, projects, funding mechanisms, and research output. It assesses how well the program supports and promotes research and scholarly activities.';
            break;
        default:
            description = 'Please answer the following questions about this section of the program assessment.';
    }
    
    // Clear previous messages
    clearMessages();
    
    // Hide text input section
    document.querySelector('.input-section').style.display = 'none';
    
    // Display section title and description
    const sectionTitle = sectionToCategoryMap[currentSection];
    addBotMessage(sectionTitle);
    addBotMessage(description);
    
    // Add proceed button
    const proceedButton = document.createElement('button');
    proceedButton.className = 'cta-button';
    proceedButton.textContent = 'Proceed to Questions';
    proceedButton.style.margin = '1rem auto';
    proceedButton.style.display = 'block';
    proceedButton.onclick = startSectionQuestions;
    
    chatMessages.appendChild(proceedButton);
}

// Start section questions
function startSectionQuestions() {
    clearMessages();
    showNextAssessmentQuestion();
}

// Update the rating buttons display
function showRatingButtons() {
    ratingButtons.innerHTML = '';
    for (let i = 1; i <= 4; i++) {
        const button = document.createElement('button');
        button.className = 'rating-btn';
        button.setAttribute('data-rating', i);
        button.setAttribute('data-label', ratingLabels[i]);
        button.innerHTML = `${i}<br><span class="rating-label">${ratingLabels[i]}</span>`;
        button.onclick = () => handleRatingSelection(i);
        ratingButtons.appendChild(button);
    }
    ratingButtons.style.display = 'flex';
    userInput.parentElement.style.display = 'none';
}

// Hide rating buttons
function hideRatingButtons() {
    ratingButtons.style.display = 'none';
    userInput.parentElement.style.display = 'flex';
}

// Update navigation
function updateNavigation() {
    // Get all navigation items
    const navItems = document.querySelectorAll('.nav-item');
    
    // Remove active and completed classes
    navItems.forEach(item => {
        item.classList.remove('active', 'completed');
    });
    
    // Mark the current section as active
    const currentNavItem = document.querySelector(`.nav-item[data-section="${state.currentSection}"]`);
    if (currentNavItem) {
        currentNavItem.classList.add('active');
    }
    
    // Mark completed sections
    const sections = Object.keys(sectionToCategoryMap);
    const currentSectionIndex = sections.indexOf(state.currentSection);
    
    for (let i = 0; i < currentSectionIndex; i++) {
        const completedNavItem = document.querySelector(`.nav-item[data-section="${sections[i]}"]`);
        if (completedNavItem) {
            completedNavItem.classList.add('completed');
        }
    }
}

// Update progress
function updateProgress() {
    // Calculate total questions
    let totalQuestions = 0;
    state.questions.categories.forEach(category => {
        totalQuestions += category.questions.length;
    });
    
    // Calculate progress percentage
    const progress = (state.assessmentResults.length / totalQuestions) * 100;
    const roundedProgress = Math.round(progress);
    
    // Update progress bar
    if (progressFill && progressText) {
        progressFill.style.width = `${progress}%`;
        progressText.textContent = `${roundedProgress}% Complete`;
    }
}

// Update handleRatingSelection
function handleRatingSelection(rating) {
    hideRatingButtons();
    
    // Get the current question
    const question = state.currentQuestions[state.currentQuestionIndex];
    
    // Add the rating to the assessment results
    state.assessmentResults.push({
        id: question.id,
        question: question.text,
        rating: rating,
        category: sectionToCategoryMap[state.currentSection]
    });
    
    // Move to the next question
    state.currentQuestionIndex++;
    
    // Update progress
    updateProgress();
    
    // Clear messages and show the next question
    clearMessages();
    showNextAssessmentQuestion();
}

// Finish the assessment
function finishAssessment() {
    clearMessages();
    addBotMessage('Thank you for completing the assessment. Generating your report...');
    generateReport();
}

// Enhance the report generation
async function generateReport() {
    try {
        showLoading('Generating recommendations...');
        
        // First, generate recommendations
        const recommendationsResponse = await fetch('/api/generate-recommendations', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                institution_info: state.institutionInfo,
                assessment_results: state.assessmentResults
            })
        });

        if (!recommendationsResponse.ok) {
            throw new Error('Failed to generate recommendations');
        }

        const recommendationsData = await recommendationsResponse.json();
        state.recommendations = recommendationsData.recommendations;

        // Then, generate the full report
        showLoading('Generating comprehensive report...');
        
        const reportResponse = await fetch('/api/generate-report', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                institution_info: state.institutionInfo,
                assessment_results: state.assessmentResults,
                recommendations: state.recommendations
            })
        });

        if (!reportResponse.ok) {
            throw new Error('Failed to generate report');
        }

        const reportData = await reportResponse.json();
        state.report = reportData.report;

        hideLoading();
        
        // Clear all previous content
        clearMessages();
        
        // Create a container for the report
        const reportContainer = document.createElement('div');
        reportContainer.className = 'report-container';
        
        // Add the report content
        const reportContent = document.createElement('div');
        reportContent.className = 'report-content';
        reportContent.innerHTML = marked.parse(state.report);
        
        // Style tables for better readability
        const tables = reportContent.querySelectorAll('table');
        tables.forEach(table => {
            table.classList.add('report-table');
            
            // Add header styling
            const headerRow = table.querySelector('thead tr');
            if (headerRow) {
                const headers = headerRow.querySelectorAll('th');
                headers.forEach(header => {
                    header.style.backgroundColor = '#2874a6';
                    header.style.color = 'white';
                });
            }
            
            // Add zebra striping
            const rows = table.querySelectorAll('tbody tr');
            rows.forEach((row, index) => {
                if (index % 2 === 1) {
                    row.style.backgroundColor = '#f5f5f5';
                }
            });
        });
        
        reportContainer.appendChild(reportContent);
        
        // Add download button
        const downloadButton = document.createElement('button');
        downloadButton.className = 'download-button';
        downloadButton.innerHTML = '<i class="fas fa-download"></i> Download Report as PDF';
        downloadButton.onclick = downloadReport;
        reportContainer.appendChild(downloadButton);
        
        // Hide the sidebar
        document.querySelector('.sidebar').style.display = 'none';
        
        // Adjust the main container to full width
        document.querySelector('.chat-container').style.marginLeft = '0';
        document.querySelector('.chat-container').style.maxWidth = '1200px';
        
        chatMessages.appendChild(reportContainer);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        // Hide the input section
        document.querySelector('.input-section').style.display = 'none';
        
    } catch (error) {
        console.error('Error generating report:', error);
        hideLoading();
        addBotMessage('There was an error generating the report. Please try again.');
    }
}

// Add download functionality
async function downloadReport() {
    try {
        showLoading('Generating PDF...');
        
        // Get the HTML content from the report
        const reportContent = document.querySelector('.report-content').innerHTML;
        
        // Send request to generate PDF
        const response = await fetch('/api/generate-pdf', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                html_content: reportContent,
                institution_info: state.institutionInfo
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to generate PDF');
        }
        
        // Convert response to blob
        const blob = await response.blob();
        
        // Create a URL for the blob
        const url = window.URL.createObjectURL(blob);
        
        // Create a temporary link and click it to download
        const a = document.createElement('a');
        a.href = url;
        a.download = `AccreditAI_${state.institutionInfo.programName.replace(/\s+/g, '_')}_Assessment_Report.pdf`;
        document.body.appendChild(a);
        a.click();
        
        // Clean up
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        hideLoading();
        
    } catch (error) {
        console.error('Error downloading report:', error);
        hideLoading();
        addBotMessage('There was an error downloading the report. Please try again.');
    }
}

// Show the next assessment question
function showNextAssessmentQuestion() {
    if (state.currentQuestionIndex < state.currentQuestions.length) {
        // Show the current question
        const question = state.currentQuestions[state.currentQuestionIndex];
        addBotMessage(question.text);
        
        // Show rating scale
        addBotMessage(`
            <div class="rating-legend">
                Rating Scale:<br>
                1 = Non-Compliant<br>
                2 = Minimal Compliance<br>
                3 = Substantial Compliance<br>
                4 = Full Compliance
            </div>
        `);
        
        // Make sure the input section is visible but hide the text input
        document.querySelector('.input-section').style.display = 'block';
        document.querySelector('.text-input').style.display = 'none';
        
        // Clear and show rating buttons
        ratingButtons.innerHTML = '';
        for (let i = 1; i <= 4; i++) {
            const button = document.createElement('button');
            button.className = 'rating-btn';
            button.setAttribute('data-rating', i);
            button.setAttribute('data-label', ratingLabels[i]);
            button.innerHTML = `${i}<br><span class="rating-label">${ratingLabels[i]}</span>`;
            button.onclick = () => handleRatingSelection(i);
            ratingButtons.appendChild(button);
        }
        
        // Make sure rating buttons are visible
        ratingButtons.style.display = 'flex';
    } else {
        // Move to the next section or finish
        const sections = Object.keys(sectionToCategoryMap);
        const currentSectionIndex = sections.indexOf(state.currentSection);
        
        if (currentSectionIndex < sections.length - 1) {
            // Move to the next section
            state.currentSection = sections[currentSectionIndex + 1];
            state.currentQuestionIndex = 0;
            
            // Find the category that matches the current section
            const category = state.questions.categories.find(
                cat => cat.name === sectionToCategoryMap[state.currentSection]
            );
            
            if (category) {
                state.currentQuestions = category.questions;
                showSectionDescription();
            } else {
                addBotMessage("Error: Could not find questions for this section. Please contact support.");
            }
        } else {
            // Finish the assessment
            finishAssessment();
        }
    }
    
    // Update navigation
    updateNavigation();
}

// Initialize the chat when the page loads
initializeChat(); 