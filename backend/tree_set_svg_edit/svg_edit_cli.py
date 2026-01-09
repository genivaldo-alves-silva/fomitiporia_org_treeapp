#!/usr/bin/env python3
# SVG editor for phylogenetic trees - CLI version
# Italicizes genus/species and bolds type specimens

import re
import xml.etree.ElementTree as ET
import sys
from pathlib import Path
import requests

# Import local check_genus module
try:
    from check_genus import check_genus
    HAS_GENUS_CHECK = True
except ImportError:
    print("⚠️ Módulo check_genus não encontrado. Verificação de gênero desativada.")
    HAS_GENUS_CHECK = False
    def check_genus(genus):
        return True  # Assume todos são válidos se módulo não disponível

def internet_connection_check():
    try:
        requests.get("https://www.google.com", timeout=3)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False

# Define SVG namespace
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace('', SVG_NS)

# Estilo para novas sequências (marcadas com neew)
NEW_SEQUENCE_STYLE = 'font-weight:bold;fill:#CC0000'  # Vermelho e negrito

# Pattern para detectar marcador neew
new_marker_pattern = re.compile(r'^neew_')

# Patterns to detect genus/species and 'type' words
genus_pattern = re.compile(
    r'(?P<genus>\b[A-Z][a-z]{3,})\s+'
    r'(?:(?P<qualifier>sp|cf|aff)\.?)?\s*'
    r'(?P<species>(?![A-Z]{2}\d)[a-zA-Z-]+)?\s*'
    r'(?P<voucher>[A-Z]+\d+[A-Za-z0-9_-]*)?(?P<tail>.*)?'
)

def process_type_words(parent_elem, text):
    """Detects and bolds type-related words like 'holotype', 'isotype', etc."""
    type_pattern = re.compile(r'(\s*)(\b(?:holo|exholo|topo|iso|ex|para|lecto|neo|epi|syn)?type\b)', re.IGNORECASE)
    last_index = 0

    for match in type_pattern.finditer(text):
        if match.start() > last_index:
            normal_text = text[last_index:match.start()]
            tspan = ET.SubElement(parent_elem, f'{{{SVG_NS}}}tspan')
            tspan.text = normal_text

        space = match.group(1)
        word = match.group(2)
        bold_tspan = ET.SubElement(parent_elem, f'{{{SVG_NS}}}tspan', attrib={'style': 'font-weight:bold'})
        bold_tspan.text = space + word

        last_index = match.end()

    if last_index < len(text):
        tspan = ET.SubElement(parent_elem, f'{{{SVG_NS}}}tspan')
        tspan.text = text[last_index:]

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
            genus_cache[genus] = check_genus(genus) if HAS_GENUS_CHECK else True

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

        # Italicize species based on qualifier type:
        # - sp. → species NOT italicized (it's just additional info, not a real epithet)
        # - cf. or aff. → species IS italicized (it's a real epithet with uncertainty)
        # - no qualifier → species IS italicized
        if species:
            if qualifier and qualifier.lower() == 'sp':
                # With "sp." qualifier - do NOT italicize what follows (not a real epithet)
                plain_species = ET.SubElement(text_elem, f'{{{SVG_NS}}}tspan')
                plain_species.text = species + ' '
            else:
                # No qualifier OR cf./aff. qualifier - italicize species
                italic_species = ET.SubElement(text_elem, f'{{{SVG_NS}}}tspan', attrib={'style': 'font-style:italic'})
                italic_species.text = species + ' '

        # Add voucher (if present)
        if voucher:
            voucher_tspan = ET.SubElement(text_elem, f'{{{SVG_NS}}}tspan')
            voucher_tspan.text = voucher

        last_index = match.end()

        # Adiciona o restante da linha após o voucher
        tail = match.group('tail')
        if tail:
            process_type_words(text_elem, tail)

    # Process remaining text
    if last_index < len(text):
        process_type_words(text_elem, text[last_index:])

def italicize_genus_species(svg_file, output_file):
    """Process SVG file and add italics/bold formatting"""
    tree = ET.parse(svg_file)
    root = tree.getroot()
    genus_cache = {}

    for text_elem in root.findall(f'.//{{{SVG_NS}}}text'):
        text = ''.join(text_elem.itertext()).strip()
        
        # Verificar se é uma nova sequência (marcada com neew)
        is_new_sequence = bool(new_marker_pattern.match(text))
        
        # Remover o marcador neew do texto
        if is_new_sequence:
            text = new_marker_pattern.sub('', text)
        
        adjusted_text = text.replace('_', ' ')

        x_attr = text_elem.get('x')
        y_attr = text_elem.get('y')

        text_elem.clear()
        if x_attr:
            text_elem.set('x', x_attr)
        if y_attr:
            text_elem.set('y', y_attr)
        
        # Se for nova sequência, aplicar estilo ao elemento pai
        if is_new_sequence:
            existing_style = text_elem.get('style', '')
            if existing_style:
                text_elem.set('style', f"{existing_style};{NEW_SEQUENCE_STYLE}")
            else:
                text_elem.set('style', NEW_SEQUENCE_STYLE)

        process_text_elements(text_elem, adjusted_text, genus_cache)

    tree.write(output_file, encoding='utf-8', xml_declaration=True)

def process_svg_file(input_svg: str, output_svg: str):
    """
    Process a single SVG file
    
    Args:
        input_svg: Path to input SVG file
        output_svg: Path to output SVG file
    """
    if not internet_connection_check() and HAS_GENUS_CHECK:
        print("⚠️ Sem conexão com a internet. Verificação de gênero desativada.")
    
    input_path = Path(input_svg)
    output_path = Path(output_svg)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input SVG not found: {input_svg}")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Processing: {input_svg}")
    italicize_genus_species(str(input_path), str(output_path))
    print(f"Output saved: {output_svg}")
    
    return str(output_path)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python svg_edit_cli.py <input_svg> <output_svg>")
        sys.exit(1)
    
    input_svg = sys.argv[1]
    output_svg = sys.argv[2]
    
    result = process_svg_file(input_svg, output_svg)
    print(f"SVG processed: {result}")
