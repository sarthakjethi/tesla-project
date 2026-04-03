import csv
from datetime import date

def load_features(filepath):
    features = []
    with open(filepath, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            features.append(row)
    return features

def check_status(features):
    counts = {"complete": 0, "in progress": 0, "delayed": 0}
    delayed = []
    for feature in features:
        status = feature["status"]
        if status in counts:
            counts[status] += 1
        if status == "delayed":
            delayed.append(feature["name"])
    return delayed, counts

def build_report(features, delayed, counts):
    lines = []
    lines.append("=== Tesla Release Tracker ===")
    lines.append(f"Date: {date.today()}")
    lines.append("---")
    lines.append("SUMMARY:")
    lines.append(f"  Total features : {len(features)}")
    lines.append(f"  Complete       : {counts['complete']}")
    lines.append(f"  In progress    : {counts['in progress']}")
    lines.append(f"  Delayed        : {counts['delayed']}")
    lines.append("---")
    for feature in features:
        lines.append(f"Feature: {feature['name']} | Status: {feature['status']} | Owner: {feature['owner']}")
    lines.append("---")
    if delayed:
        lines.append("FLAGGED AS DELAYED:")
        for item in delayed:
            lines.append(f" - {item}")
    else:
        lines.append("No delayed features.")
    return lines

def print_report(features, delayed, counts, output_path="data/report.txt"):
    lines = build_report(features, delayed, counts)
    for line in lines:
        print(line)
    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")

features = load_features("data/releases.csv")
delayed, counts = check_status(features)
print_report(features, delayed, counts)
