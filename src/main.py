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

def print_report(features, delayed, counts):
    print("=== Tesla Release Tracker ===")
    print("Date:", date.today())
    print("---")
    print("SUMMARY:")
    print(f"  Total features : {len(features)}")
    print(f"  Complete       : {counts['complete']}")
    print(f"  In progress    : {counts['in progress']}")
    print(f"  Delayed        : {counts['delayed']}")
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
delayed, counts = check_status(features)
print_report(features, delayed, counts)
