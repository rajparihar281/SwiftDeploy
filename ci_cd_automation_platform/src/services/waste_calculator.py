import yaml
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

def load_config():
    with open(CONFIG_PATH, "r") as file:
        return yaml.safe_load(file)

def calculate_waste_score(cpu, memory, build_time):
    config = load_config()
    thresholds = config["thresholds"]
    weights = config["weights"]

    normalized_cpu = cpu / thresholds["cpu_max"]
    normalized_memory = memory / thresholds["memory_max"]
    normalized_time = build_time / thresholds["build_time_max"]

    waste_score = (
        weights["cpu"] * normalized_cpu +
        weights["memory"] * normalized_memory +
        weights["time"] * normalized_time
    ) * 100

    return round(waste_score, 2)