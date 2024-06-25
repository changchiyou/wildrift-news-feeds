import xml.etree.ElementTree as ET
import os
import glob

def check_xml(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    entries = root.findall('.//item')
    if len(entries) == 0:
        raise ValueError(f"No entries found in {file_path}")
    else:
        print(f"{file_path} contains {len(entries)} entries.")

# Define the directory containing the generated XML files
directory_path = "public/"

# Check all XML files in the specified directory
xml_files = glob.glob(os.path.join(directory_path, "*.xml"))

if not xml_files:
    raise FileNotFoundError(f"No XML files found in {directory_path}")

for xml_file in xml_files:
    check_xml(xml_file)