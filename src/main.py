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
    delayed = []
    for feature in features:
        if feature["status"] == "delayed":
            delayed.append(feature["name"])
    return delayed

def print_report(features, delayed):
    print("=== Tesla Release Tracker ===")
    print("Date:", date.today())
    print("---")
    for feature in features:
        print("Feature:", feature["name"], "| Status:", feature["status"], "| Owner:", feature["owner"])
    print("---")
    if delayed:
        print("FLAGGED AS DELAYED:")
        for item in delayed:
            print(" -", item)
    else:
        print("No delayed features.")

features = load_features("data/releases.csv")
delayed = check_status(features)
print_report(features, delayed)
