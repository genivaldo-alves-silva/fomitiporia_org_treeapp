## Tree visualization with support values
##
import html  # To escape XML-invalid characters
import toytree
import re
import toyplot.pdf
import toyplot.png
import toyplot.svg

# Load the tree from the URL
tree_url = "tree.tre"
tree = toytree.tree(tree_url)

# Find tips that match 'outgroup'
matching_tips = [name for name in tree.get_tip_labels() if 'uncisetus' in name]

# Root the tree using the MRCA of the matched tips
if matching_tips:
    # Get the MRCA of the matched tips
    mrca = tree.get_mrca_node(*matching_tips)
    rooted_tree = tree.root(mrca)

# Ladderize the tree
ladderized_tree = rooted_tree.ladderize()

# Create a node label list for all nodes (internal and terminal)
node_labels = ['' for _ in range(ladderized_tree.nnodes)]

# Create a node size list for all nodes (internal and terminal)
node_sizes = [0 for _ in range(ladderized_tree.nnodes)]  # Initialize with size 0

# Create a node marker list (alternatives to circles)
# Use "s" for squares, "t" for triangles, "d" for diamonds, etc.
node_markers = ['' for _ in range(ladderized_tree.nnodes)]  # Initialize empty

# Create a node color list
node_colors = ['black' for _ in range(ladderized_tree.nnodes)]  # Default color is black

# Traverse all internal nodes and add support labels and sizes where support >= 60
for node in ladderized_tree.treenode.traverse():
    if node.is_leaf():
        continue  # Skip terminal nodes
    # Get the support value
    support_value = node.support
    # Only label and add a marker if support is 50 or higher
    if support_value is not None and support_value >= 50:
        # Convert the support value to an integer to remove the decimal part
        node_labels[node.idx] = str(int(support_value))  # Format support as an integer
        node_sizes[node.idx] = 15  # Set a size for markers where support >= 60
        node_markers[node.idx] = "s"  # Use squares for nodes with support >= 60

# Draw the tree with custom tip labels, node sizes, markers, and colors
canvas, axes, mark = ladderized_tree.draw(
    width=1700,
    height=4000,
    tip_labels_align=False,
    tip_labels_style={  # Font style for tip labels
        "fill": "#262626",          # Text color
        "font-size": "20px",        # Font size in pixels
        "-toyplot-anchor-shift": "15px",  # Adjust label position
    },
    node_labels=node_labels,          # Set to None to hide support values
    node_labels_style={  # Font style for tip labels
        "fill": "#262626",          # Text color
        "font-size": "15px",        # Font size in pixels
    },
    node_sizes=None,     # Set node sizes: 0 for support < 50, adjusted sizes for others
    node_markers=node_markers, # Set the marker types (circle, square, diamond)
    node_colors=node_colors,   # Set node colors (black, gray, red)
    edge_style={
        "stroke": "black", 
        "stroke-width": 1,
    },
)

# Save the canvas to different formats
#toyplot.pdf.render(canvas, "tree_visualization.pdf")
#toyplot.png.render(canvas, "tree_visualization.png")
toyplot.svg.render(canvas, "out/supportvalue.svg")