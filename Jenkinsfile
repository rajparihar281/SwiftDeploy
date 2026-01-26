pipeline {
    agent any

    environment {
        IMAGE_NAME = "cicd-mvp-app"
        CONTAINER_NAME = "cicd-mvp-container"
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build') {
            steps {
                bat '''
                py -3.12 -m venv venv
                venv\\Scripts\\python -m pip install --upgrade pip
                venv\\Scripts\\python -m pip install -r requirements.txt
                '''
            }
        }

        stage('Test') {
            steps {
                bat '''
                venv\\Scripts\\python -m pytest
                '''
            }
        }

        stage('Docker Build') {
            steps {
                bat '''
                docker build -t %IMAGE_NAME% .
                '''
            }
        }

        stage('Docker Deploy') {
    steps {
        bat '''
        docker ps -a | findstr %CONTAINER_NAME% && docker stop %CONTAINER_NAME% || echo Container not running
        docker ps -a | findstr %CONTAINER_NAME% && docker rm %CONTAINER_NAME% || echo Container not present
        docker run -d -p 5000:5000 --name %CONTAINER_NAME% %IMAGE_NAME%
        '''
    }
}

    }

    post {
        success {
            echo '🚀 CI/CD pipeline completed. App deployed in Docker.'
        }
        failure {
            echo '❌ Pipeline failed. Deployment aborted.'
        }
    }
}
