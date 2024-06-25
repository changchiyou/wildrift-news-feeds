import xml.etree.ElementTree as ET
import os
import glob

def check_xml(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Register namespaces to handle namespaces in the XML file
    namespaces = {'atom': 'http://www.w3.org/2005/Atom'}

    # Check for Atom <entry> elements
    atom_entries = root.findall('.//atom:entry', namespaces)
    # Check for RSS <item> elements
    rss_items = root.findall('.//item')

    if len(atom_entries) == 0 and len(rss_items) == 0:
        raise ValueError(f"No entries found in {file_path}")
    else:
        print(f"{file_path} contains {len(atom_entries)} Atom entries and {len(rss_items)} RSS items.")


# Define the directory containing the generated XML files
directory_path = "public/"

# Check all XML files in the specified directory
xml_files = glob.glob(os.path.join(directory_path, "*.xml"))

if not xml_files:
    raise FileNotFoundError(f"No XML files found in {directory_path}")

for xml_file in xml_files:
    check_xml(xml_file)