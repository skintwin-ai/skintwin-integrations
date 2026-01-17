class SkillTutorial {
    constructor(options = {}) {
        this.isDarkTheme = document.querySelector('html').getAttribute('data-bs-theme') === 'dark';
        this.options = {
            startAutomatically: true,
            showProgress: true,
            dismissible: true,
            completionCookieName: 'skill_tutorial_completed',
            completionCookieExpiry: 365, // days
            ...options
        };
        
        this.currentStep = 0;
        this.tutorialSteps = [
            {
                title: 'Welcome to the AI Skill Playground!',
                content: 'This interactive platform allows you to train AI models in various skincare-related skills. Your AI assistant will learn from your expertise to deliver better client experiences and streamline salon operations.',
                position: 'center',
                element: null
            },
            {
                title: 'Explore Skin Analysis Skills',
                content: 'Train AI to recognize skin conditions, analyze treatment effectiveness, and provide personalized skincare recommendations based on client data.',
                position: 'bottom',
                element: '.card-header h5'
            },
            {
                title: 'Skill Difficulty Levels',
                content: 'Each skill is rated from 1-5 stars for difficulty. Begin with foundational skills like Basic Pattern Recognition before advancing to Complex Data Analysis.',
                position: 'right',
                element: '.fas.fa-star'
            },
            {
                title: 'Your Skill Progress',
                content: 'The progress bar shows your advancement in each skill. Complete training sessions to gain experience points and increase your mastery level.',
                position: 'bottom',
                element: '.progress'
            },
            {
                title: 'Interactive Training',
                content: 'Click Train to start an interactive session where you\'ll provide examples and feedback to help the AI learn skincare concepts and improve its recommendations.',
                position: 'top',
                element: '.btn-primary'
            },
            {
                title: 'Professional Achievements',
                content: 'Earn professional achievements like "Skin Analysis Expert" and "Treatment Optimization Guru" as you master AI skills. These showcase your expertise in AI-powered skincare.',
                position: 'left',
                element: 'a[href*="achievements"]'
            },
            {
                title: 'Create AI Models',
                content: 'Your training sessions create specialized AI models that can be applied in your salon for skin analysis, product recommendations, and treatment optimization.',
                position: 'left',
                element: 'a[href*="models"]'
            },
            {
                title: 'Professional Leaderboard',
                content: 'See how your AI training compares with other skincare professionals. The leaderboard shows top performers based on achievements and skill mastery.',
                position: 'left',
                element: 'a[href*="leaderboard"]'
            },
            {
                title: 'Enhance Your Salon Experience!',
                content: 'By training these AI skills, you\'re creating a more personalized and effective experience for your clients while optimizing your salon operations. Start with your first skill now!',
                position: 'center',
                element: null
            }
        ];

        this.init();
    }

    init() {
        this.createTutorialElements();
        
        if (this.options.startAutomatically && !this.hasCompletedTutorial()) {
            this.startTutorial();
        }
    }

    createTutorialElements() {
        // Create overlay
        this.overlay = document.createElement('div');
        this.overlay.className = 'tutorial-overlay';
        document.body.appendChild(this.overlay);

        // Create modal
        this.modal = document.createElement('div');
        this.modal.className = `tutorial-modal ${this.isDarkTheme ? 'dark-theme' : ''}`;
        
        // Create modal header
        const modalHeader = document.createElement('div');
        modalHeader.className = 'tutorial-header';
        
        this.modalTitle = document.createElement('h4');
        modalHeader.appendChild(this.modalTitle);
        
        if (this.options.dismissible) {
            const closeButton = document.createElement('button');
            closeButton.className = 'tutorial-close';
            closeButton.innerHTML = '&times;';
            closeButton.addEventListener('click', () => this.endTutorial());
            modalHeader.appendChild(closeButton);
        }
        
        this.modal.appendChild(modalHeader);
        
        // Create modal content
        this.modalContent = document.createElement('div');
        this.modalContent.className = 'tutorial-content';
        this.modal.appendChild(this.modalContent);
        
        // Create navigation buttons
        const modalNav = document.createElement('div');
        modalNav.className = 'tutorial-navigation';
        
        this.prevButton = document.createElement('button');
        this.prevButton.className = 'tutorial-btn tutorial-btn-outline';
        this.prevButton.textContent = 'Previous';
        this.prevButton.addEventListener('click', () => this.previousStep());
        
        this.skipButton = document.createElement('button');
        this.skipButton.className = 'tutorial-btn tutorial-btn-secondary';
        this.skipButton.textContent = 'Skip Tutorial';
        this.skipButton.addEventListener('click', () => this.endTutorial());
        
        this.nextButton = document.createElement('button');
        this.nextButton.className = 'tutorial-btn tutorial-btn-primary';
        this.nextButton.textContent = 'Next';
        this.nextButton.addEventListener('click', () => this.nextStep());
        
        modalNav.appendChild(this.prevButton);
        modalNav.appendChild(this.skipButton);
        modalNav.appendChild(this.nextButton);
        this.modal.appendChild(modalNav);
        
        // Create progress dots
        if (this.options.showProgress) {
            this.progressContainer = document.createElement('div');
            this.progressContainer.className = 'tutorial-progress';
            
            for (let i = 0; i < this.tutorialSteps.length; i++) {
                const dot = document.createElement('div');
                dot.className = 'tutorial-dot';
                this.progressContainer.appendChild(dot);
            }
            
            this.modal.appendChild(this.progressContainer);
        }
        
        document.body.appendChild(this.modal);
        
        // Create spotlight
        this.spotlight = document.createElement('div');
        this.spotlight.className = 'tutorial-spotlight';
        document.body.appendChild(this.spotlight);
        
        // Create tooltip
        this.tooltip = document.createElement('div');
        this.tooltip.className = `tutorial-tooltip ${this.isDarkTheme ? 'dark-theme' : ''}`;
        document.body.appendChild(this.tooltip);
    }

    startTutorial() {
        document.body.style.overflow = 'hidden';
        this.overlay.style.display = 'block';
        this.goToStep(0);
    }

    endTutorial() {
        document.body.style.overflow = '';
        this.overlay.style.display = 'none';
        this.modal.style.display = 'none';
        this.spotlight.style.display = 'none';
        this.tooltip.style.display = 'none';
        
        this.setTutorialCompleted();
    }

    goToStep(stepIndex) {
        this.currentStep = stepIndex;
        const step = this.tutorialSteps[stepIndex];
        
        // Update modal content
        this.modalTitle.textContent = step.title;
        this.modalContent.textContent = step.content;
        
        // Update navigation buttons
        this.prevButton.style.visibility = stepIndex > 0 ? 'visible' : 'hidden';
        
        const isLastStep = stepIndex === this.tutorialSteps.length - 1;
        this.nextButton.textContent = isLastStep ? 'Finish' : 'Next';
        
        // Update progress dots
        if (this.options.showProgress) {
            const dots = this.progressContainer.querySelectorAll('.tutorial-dot');
            dots.forEach((dot, i) => {
                dot.className = i === stepIndex ? 'tutorial-dot active' : 'tutorial-dot';
            });
        }
        
        // Show modal for first and last steps, otherwise show tooltip
        if (step.position === 'center') {
            this.spotlight.style.display = 'none';
            this.tooltip.style.display = 'none';
            this.modal.style.display = 'block';
            return;
        }
        
        // Find element to highlight
        let targetElement;
        try {
            targetElement = document.querySelector(step.element);
        } catch (e) {
            // Handle case where selector is invalid
            console.error(`Invalid selector for step ${stepIndex}:`, e);
            targetElement = null;
        }
        
        // If element not found or position is center, show modal
        if (!targetElement) {
            this.spotlight.style.display = 'none';
            this.tooltip.style.display = 'none';
            this.modal.style.display = 'block';
            return;
        }
        
        // Hide modal and setup spotlight
        this.modal.style.display = 'none';
        
        // Position spotlight
        const rect = targetElement.getBoundingClientRect();
        this.spotlight.style.display = 'block';
        this.spotlight.style.top = `${rect.top}px`;
        this.spotlight.style.left = `${rect.left}px`;
        this.spotlight.style.width = `${rect.width}px`;
        this.spotlight.style.height = `${rect.height}px`;
        
        // Position tooltip
        this.tooltip.style.display = 'block';
        this.tooltip.innerHTML = `<strong>${step.title}</strong><br>${step.content}`;
        
        // Remove previous position classes
        this.tooltip.classList.remove('top', 'bottom', 'left', 'right');
        this.tooltip.classList.add(step.position);
        
        let tooltipX, tooltipY;
        
        switch (step.position) {
            case 'top':
                tooltipX = rect.left + rect.width / 2;
                tooltipY = rect.top - 10;
                this.tooltip.style.transform = 'translate(-50%, -100%)';
                break;
            case 'bottom':
                tooltipX = rect.left + rect.width / 2;
                tooltipY = rect.bottom + 10;
                this.tooltip.style.transform = 'translate(-50%, 0)';
                break;
            case 'left':
                tooltipX = rect.left - 10;
                tooltipY = rect.top + rect.height / 2;
                this.tooltip.style.transform = 'translate(-100%, -50%)';
                break;
            case 'right':
                tooltipX = rect.right + 10;
                tooltipY = rect.top + rect.height / 2;
                this.tooltip.style.transform = 'translate(0, -50%)';
                break;
        }
        
        this.tooltip.style.left = `${tooltipX}px`;
        this.tooltip.style.top = `${tooltipY}px`;
    }

    nextStep() {
        if (this.currentStep < this.tutorialSteps.length - 1) {
            this.goToStep(this.currentStep + 1);
        } else {
            this.endTutorial();
        }
    }

    previousStep() {
        if (this.currentStep > 0) {
            this.goToStep(this.currentStep - 1);
        }
    }

    hasCompletedTutorial() {
        return document.cookie.split(';').some(cookie => 
            cookie.trim().startsWith(`${this.options.completionCookieName}=true`));
    }

    setTutorialCompleted() {
        const expiryDate = new Date();
        expiryDate.setDate(expiryDate.getDate() + this.options.completionCookieExpiry);
        document.cookie = `${this.options.completionCookieName}=true; expires=${expiryDate.toUTCString()}; path=/`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Only show tutorial on the skills playground pages
    const isSkillsPage = window.location.pathname.includes('/skills');
    if (isSkillsPage) {
        const tutorial = new SkillTutorial();
        
        // Add tutorial button to skill page
        const skillsHeader = document.querySelector('.container h1');
        if (skillsHeader && !document.querySelector('.tutorial-button')) {
            const tutorialButton = document.createElement('button');
            tutorialButton.className = 'btn btn-info ms-3 tutorial-button';
            tutorialButton.innerHTML = '<i class="fas fa-graduation-cap"></i> Interactive Tutorial';
            tutorialButton.addEventListener('click', (e) => {
                e.preventDefault();
                tutorial.startTutorial();
            });
            
            skillsHeader.appendChild(tutorialButton);
        }
        
        // Add tutorial initialization to navbar
        const navbarItems = document.querySelectorAll('.navbar-nav .nav-item');
        const lastNavItem = navbarItems[navbarItems.length - 1];
        
        if (lastNavItem && !document.querySelector('.tutorial-nav-item')) {
            const tutorialLi = document.createElement('li');
            tutorialLi.className = 'nav-item tutorial-nav-item';
            
            const tutorialLink = document.createElement('a');
            tutorialLink.className = 'nav-link';
            tutorialLink.href = '#';
            tutorialLink.innerHTML = '<i class="fas fa-graduation-cap"></i> Interactive Tutorial';
            tutorialLink.addEventListener('click', (e) => {
                e.preventDefault();
                tutorial.startTutorial();
            });
            
            tutorialLi.appendChild(tutorialLink);
            lastNavItem.parentNode.insertBefore(tutorialLi, lastNavItem.nextSibling);
        }
    }
});