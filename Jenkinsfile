pipeline {
    agent any

    stages {

        stage('Checkout') {
            steps {
                echo 'Checking out source code...'
                checkout scm
            }
        }

        stage('Build') {
            steps {
                echo 'Setting up Python 3.12 virtual environment and installing dependencies...'
                bat '''
                py -3.12 --version
                py -3.12 -m venv venv
                venv\\Scripts\\python -m pip install --upgrade pip
                venv\\Scripts\\python -m pip install -r requirements.txt
                '''
            }
        }

        stage('Test') {
            steps {
                echo 'Running unit tests...'
                bat '''
                venv\\Scripts\\python -m pytest
                '''
            }
        }
    }

    post {
        success {
            echo '✅ CI Pipeline completed successfully!'
        }
        failure {
            echo '❌ CI Pipeline failed. Fix errors before deploying.'
        }
    }
}
