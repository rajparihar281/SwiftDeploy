pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build & Test') {
            steps {
                bat '''
                py -3.12 -m venv venv
                venv\\Scripts\\python -m pip install --upgrade pip
                venv\\Scripts\\python -m pip install -r requirements.txt
                venv\\Scripts\\python -m pytest
                '''
            }
        }

        stage('Docker Build') {
            steps {
                bat 'docker build -t cicd-mvp-app .'
            }
        }

        stage('Docker Deploy') {
            steps {
                bat '''
                docker ps -a | findstr cicd-mvp-container && docker stop cicd-mvp-container
                docker ps -a | findstr cicd-mvp-container && docker rm cicd-mvp-container
                docker run -d -p 5000:5000 --name cicd-mvp-container cicd-mvp-app
                '''
            }
        }
    }

    post {
        success {
            echo '🚀 CI/CD completed. App running on http://localhost:5000'
        }
        failure {
            echo '❌ Pipeline failed.'
        }
    }
}
