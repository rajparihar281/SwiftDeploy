import sqlite3
import os
from datetime import datetime
import json

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "builds.db")


class ReportBuilder:

    @staticmethod
    def generate_build_id():
        return datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    @staticmethod
    def build_report(metrics, decision_data, test_status):
        report = {
            "build_id": ReportBuilder.generate_build_id(),
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": metrics,
            "waste_score": decision_data["waste_score"],
            "decision": decision_data["decision"],
            "violations": decision_data["violations"],
            "test_status": test_status
        }

        return report

    @staticmethod
    def save_to_database(report):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO builds (build_id, waste_score, decision, timestamp)
            VALUES (?, ?, ?, ?)
        """, (
            report["build_id"],
            report["waste_score"],
            report["decision"],
            report["timestamp"]
        ))

        conn.commit()
        conn.close()

    @staticmethod
    def fetch_all_builds():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM builds ORDER BY id DESC")
        rows = cursor.fetchall()

        conn.close()
        return rows
    
    
    @staticmethod
    def fetch_latest_build():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT build_id, waste_score, decision, timestamp
        FROM builds
        ORDER BY id DESC
        LIMIT 1""")
        row = cursor.fetchone()
        
        conn.close()
        return row