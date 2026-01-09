#!/usr/bin/env python3
## Tree visualization with support values - CLI version
##
import html
import toytree
import re
import toyplot.svg
import sys
from pathlib import Path
from ete3 import Tree

# Default outgroup para enraizamento da árvore
DEFAULT_OUTGROUP = "uncisetus"

# Dimensões padrão do SVG
DEFAULT_WIDTH = 1700
DEFAULT_HEIGHT = 4000

# Altura base por sequência (multiplicador)
HEIGHT_PER_SEQUENCE = 23

def count_sequences_in_alignment(alignment_file: str) -> int:
    """
    Conta o número de sequências em um arquivo FASTA de alinhamento.
    Cada sequência começa com '>'.
    
    Args:
        alignment_file: Caminho para o arquivo de alinhamento FASTA
    
    Returns:
        Número de sequências (contagem de '>')
    """
    try:
        with open(alignment_file, 'r') as f:
            content = f.read()
            return content.count('>')
    except Exception as e:
        print(f"Erro ao ler arquivo de alinhamento: {e}")
        return 0

def calculate_tree_height(alignment_file: str = None) -> int:
    """
    Calcula a altura da árvore baseada no número de sequências.
    Altura = número de sequências * 23
    
    Args:
        alignment_file: Caminho para o arquivo de alinhamento FASTA
    
    Returns:
        Altura calculada para a árvore SVG
    """
    if alignment_file:
        num_sequences = count_sequences_in_alignment(alignment_file)
        if num_sequences > 0:
            calculated_height = num_sequences * HEIGHT_PER_SEQUENCE
            print(f"Altura calculada: {num_sequences} sequências * {HEIGHT_PER_SEQUENCE} = {calculated_height}px")
            return calculated_height
    
    print(f"Usando altura padrão: {DEFAULT_HEIGHT}px")
    return DEFAULT_HEIGHT

def generate_tree_svg(tree_file: str, output_dir: str, outgroup: str = DEFAULT_OUTGROUP, 
                      alignment_file: str = None, width: int = None, height: int = None):
    """
    Gera SVG da árvore filogenética com valores de suporte
    
    Args:
        tree_file: Caminho para arquivo .tre (Newick)
        output_dir: Diretório onde salvar o SVG
        outgroup: String para buscar nas tips e usar como outgroup para enraizamento
        alignment_file: Arquivo FASTA para calcular altura automática
        width: Largura do SVG em pixels (default: 1700)
        height: Altura do SVG em pixels (se None, calcula baseado no alinhamento)
    """
    t = Tree(tree_file, format=0)
    t.write(outfile=output_dir + "/temp.tre", format=0)
    # Load the tree
    tree = toytree.tree(output_dir + "/temp.tre")
    
    # Find tips that match outgroup for rooting
    matching_tips = [name for name in tree.get_tip_labels() if outgroup.lower() in name.lower()]
    
    # Root the tree using the MRCA of the matched tips (se encontrado)
    if matching_tips:
        mrca = tree.get_mrca_node(*matching_tips)
        rooted_tree = tree.root(mrca)
        print(f"Árvore enraizada usando outgroup '{outgroup}' ({len(matching_tips)} tips encontradas)")
    else:
        rooted_tree = tree
        print(f"Aviso: Outgroup '{outgroup}' não encontrado, árvore não enraizada")
    
    # Ladderize the tree
    ladderized_tree = rooted_tree.ladderize()
    
    # Create node label list for all nodes (internal and terminal)
    node_labels = ['' for _ in range(ladderized_tree.nnodes)]
    
    # Create node size list
    node_sizes = [0 for _ in range(ladderized_tree.nnodes)]
    
    # Create node marker list
    node_markers = ['' for _ in range(ladderized_tree.nnodes)]
    
    # Create node color list
    node_colors = ['black' for _ in range(ladderized_tree.nnodes)]
    
    # Traverse all internal nodes and add support labels where support >= 50
    for node in ladderized_tree.treenode.traverse():
        if node.is_leaf():
            continue
        support_value = node.support
        if support_value is not None and support_value >= 50:
            node_labels[node.idx] = str(int(support_value))
            node_sizes[node.idx] = 15
            node_markers[node.idx] = "s"
    
    # Calcular altura baseada no alinhamento (se height não foi especificado)
    if height is None:
        tree_height = calculate_tree_height(alignment_file)
    else:
        tree_height = height
        print(f"Usando altura customizada: {tree_height}px")
    
    # Usar width padrão se não especificado
    tree_width = width if width is not None else DEFAULT_WIDTH
    print(f"Dimensões do SVG: {tree_width}px x {tree_height}px")
    
    # Draw the tree
    canvas, axes, mark = ladderized_tree.draw(
        width=tree_width,
        height=tree_height,
        tip_labels_align=False,
        tip_labels_style={
            "fill": "#262626",
            "font-size": "20px",
            "-toyplot-anchor-shift": "15px",
        },
        node_labels=node_labels,
        node_labels_style={
            "fill": "#262626",
            "font-size": "15px",
        },
        node_sizes=None,
        node_markers=node_markers,
        node_colors=node_colors,
        edge_style={
            "stroke": "black", 
            "stroke-width": 1,
        },
    )
    
    # Save to output directory
    output_path = Path(output_dir) / "supportvalue.svg"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    toyplot.svg.render(canvas, str(output_path))
    
    return str(output_path)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python tree_set_cli.py <tree_file> <output_dir> [outgroup] [alignment_file] [width] [height]")
        print(f"  outgroup: String para buscar nas tips (default: '{DEFAULT_OUTGROUP}')")
        print(f"  alignment_file: Arquivo FASTA para calcular altura (altura = nº sequências * {HEIGHT_PER_SEQUENCE})")
        print(f"  width: Largura do SVG em pixels (default: {DEFAULT_WIDTH})")
        print(f"  height: Altura do SVG em pixels (default: calculado ou {DEFAULT_HEIGHT})")
        sys.exit(1)
    
    tree_file = sys.argv[1]
    output_dir = sys.argv[2]
    outgroup = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_OUTGROUP
    
    # alignment_file pode ser string vazia (quando width/height são passados sem alignment)
    alignment_file = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else None
    
    # width e height podem ser strings vazias
    width = int(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5] else None
    height = int(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[6] else None
    
    output_svg = generate_tree_svg(tree_file, output_dir, outgroup, alignment_file, width, height)
    print(f"SVG generated: {output_svg}")
