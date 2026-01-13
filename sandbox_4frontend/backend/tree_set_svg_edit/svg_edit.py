# need internet connection
# #is bolding

import re
import xml.etree.ElementTree as ET
import os
import requests
from check_genus import check_genus

def internet_connection_check():
    try:
        requests.get("https://www.google.com", timeout=3)
        return True
    except requests.ConnectionError:
        return False

if not internet_connection_check():
    print("⚠️ Sem conexão com a internet. Verificação de gênero será desativada.")

# Define SVG namespace
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace('', SVG_NS)  # Ensure correct namespace handling


# Patterns to detect genus/species and 'type' words
type_pattern = re.compile(r'\b(\w*type\w*)\b', re.IGNORECASE)
genus_pattern = re.compile(
    r'(?P<genus>\b[A-Z][a-z]{3,})\s+'
    r'(?:(?P<qualifier>sp|cf|aff)\.?)?\s*'
    r'(?P<species>(?![A-Z]{2}\d)[a-zA-Z-]+)?\s*'
    r'(?P<voucher>[A-Z]+\d+[A-Za-z0-9_-]*)?(?P<tail>.*)?'
)

#r'(?P<voucher>[A-Z][\w]*\s*\d+.*)?'

def italicize_genus_species(svg_file, output_file):
    tree = ET.parse(svg_file)
    root = tree.getroot()
    genus_cache = {}

    for text_elem in root.findall(f'.//{{{SVG_NS}}}text'):
        text = ''.join(text_elem.itertext()).strip()
        adjusted_text = text.replace('_', ' ')

        x_attr = text_elem.get('x')
        y_attr = text_elem.get('y')

        text_elem.clear()
        if x_attr:
            text_elem.set('x', x_attr)
        if y_attr:
            text_elem.set('y', y_attr)

        last_index = 0

        # Process genus/species with italics and 'type' words with bold
        process_text_elements(text_elem, adjusted_text, genus_cache)

    tree.write(output_file, encoding='utf-8', xml_declaration=True)

def process_text_elements(text_elem, text, genus_cache):
    """Handles both italics for genus/species and bold for 'type' words."""
    matches = list(genus_pattern.finditer(text))
    last_index = 0

    for match in matches:
        genus, qualifier, species, voucher = (
            match.group('genus'), match.group('qualifier'),
            match.group('species'), match.group('voucher')
        )

        if genus not in genus_cache:
            genus_cache[genus] = check_genus(genus)

        # Add plain text before the match
        if match.start() > last_index:
            plain_text = text[last_index:match.start()]
            process_type_words(text_elem, plain_text)

        # Italicize genus if valid
        if genus_cache[genus]:
            italic_genus = ET.SubElement(text_elem, f'{{{SVG_NS}}}tspan', attrib={'style': 'font-style:italic'})
            italic_genus.text = genus + ' '
        else:
            plain_genus = ET.SubElement(text_elem, f'{{{SVG_NS}}}tspan')
            plain_genus.text = genus + ' '

        # Add qualifier if present
        if qualifier:
            qualifier_tspan = ET.SubElement(text_elem, f'{{{SVG_NS}}}tspan')
            qualifier_tspan.text = f"{qualifier}." + ' '

        # Italicize species (only if present)
        if species:
            italic_species = ET.SubElement(text_elem, f'{{{SVG_NS}}}tspan', attrib={'style': 'font-style:italic'})
            italic_species.text = species + ' '

        # Add voucher (if present)
        if voucher:
            voucher_tspan = ET.SubElement(text_elem, f'{{{SVG_NS}}}tspan')
            voucher_tspan.text = voucher  # sem espaço extra!

        last_index = match.end()

        # Adiciona o restante da linha após o voucher
        tail = match.group('tail')
        if tail:
            process_type_words(text_elem, tail)

    # Process remaining text (caso nada tenha sido capturado pela regex)
    if last_index < len(text):
        process_type_words(text_elem, text[last_index:])


def process_type_words(parent_elem, text):
    """Detects and bolds type-related words like 'holotype', 'isotype', etc., preserving spacing."""
    type_pattern = re.compile(r'(\s*)(\b(?:holo|exholo|topo|iso|ex|para|lecto|neo|epi|syn)?type\b)', re.IGNORECASE)
    last_index = 0

    for match in type_pattern.finditer(text):
        # Adiciona texto normal antes da correspondência
        if match.start() > last_index:
            normal_text = text[last_index:match.start()]
            tspan = ET.SubElement(parent_elem, f'{{{SVG_NS}}}tspan')
            tspan.text = normal_text

        space = match.group(1)
        word = match.group(2)
        bold_tspan = ET.SubElement(parent_elem, f'{{{SVG_NS}}}tspan', attrib={'style': 'font-weight:bold'})
        bold_tspan.text = space + word

        last_index = match.end()

    # Adiciona o restante do texto
    if last_index < len(text):
        tspan = ET.SubElement(parent_elem, f'{{{SVG_NS}}}tspan')
        tspan.text = text[last_index:]

def process_svg_folder(input_folder):
    for file_name in os.listdir(input_folder):
        if file_name.endswith('.svg'):
            input_file = os.path.join(input_folder, file_name)
            base_name = os.path.splitext(file_name)[0]
            output_file = os.path.join(input_folder, f"{base_name}_output.svg")

            print(f"Processing file: {input_file}")
            italicize_genus_species(input_file, output_file)
            print(f"Output saved to: {output_file}")

# Example usage
svg_input_folder = 'out/'  # Adjust path as needed
process_svg_folder(svg_input_folder)
