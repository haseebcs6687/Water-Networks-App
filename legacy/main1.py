import streamlit as st
import networkx as nx
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Circle


def visualize_graph():
    G = nx.Graph()
    node_colors = {
        'junction': 'skyblue',
        'tank': 'gold',
        'reservoir': 'salmon'
    }

    # Add nodes
    for node in st.session_state.nodes:
        G.add_node(node['id'], type=node['type'])

    # Add edges with pump information
    for pipe in st.session_state.pipes:
        edge_attrs = {}
        if pipe['has_pump']:
            edge_attrs['style'] = 'dashed'
            edge_attrs['label'] = f"Pump ({pipe['pump_power']}kW)"
        G.add_edge(pipe['start'], pipe['end'], **edge_attrs)

    # Draw graph
    pos = nx.spring_layout(G, seed=42)
    fig, ax = plt.subplots(figsize=(10, 8))

    # Draw nodes
    for node_type, color in node_colors.items():
        nx.draw_networkx_nodes(G, pos,
                               nodelist=[n['id'] for n in st.session_state.nodes if n['type'] == node_type],
                               node_color=color,
                               node_size=1000,
                               ax=ax)

    # Draw regular pipes
    regular_pipes = [(u, v) for u, v, d in G.edges(data=True) if 'style' not in d]
    nx.draw_networkx_edges(G, pos, edgelist=regular_pipes, width=2, ax=ax)

    # Draw pumped pipes
    pumped_pipes = [(u, v) for u, v, d in G.edges(data=True) if 'style' in d]
    nx.draw_networkx_edges(G, pos, edgelist=pumped_pipes, width=2, style='dashed', ax=ax)

    # Add labels and legend
    nx.draw_networkx_labels(G, pos, font_size=10, ax=ax)
    edge_labels = nx.get_edge_attributes(G, 'label')
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, ax=ax)

    # Create legend
    legend_elements = [
        Circle(0, color='skyblue', label='Junction'),
        Circle(0, color='gold', label='Tank'),
        Circle(0, color='salmon', label='Reservoir'),
        plt.Line2D([0], [0], color='black', linestyle='--', label='Pump')
    ]
    ax.legend(handles=legend_elements, loc='upper right')
    plt.title("Water Network Graph")
    st.pyplot(fig)


def create_network_matrices(nodes, pipes):
    """Create matrices with all pipe flows labeled correctly"""
    # Calculate components
    non_pumped = sum(1 for p in pipes if not p['has_pump'])
    pumped = len(pipes) - non_pumped
    junctions = sum(1 for n in nodes if n['type'] == 'junction')
    reservoirs = sum(1 for n in nodes if n['type'] == 'reservoir')
    tanks = sum(1 for n in nodes if n['type'] == 'tank')

    # Calculate matrix dimension using original formula
    K = (len(pipes) + 2 * non_pumped + junctions + reservoirs + tanks)

    # Initialize E matrix
    E = [[0] * K for _ in range(K)]

    # Set diagonals for non-pumped pipes
    for i in range(non_pumped):
        E[i][i] = 1

    # Set diagonals for tanks (bottom rows)
    tank_start = K - tanks
    for i in range(tank_start, K):
        E[i][i] = 1

    return {
        'E_matrix': E,
        'components': {
            'non_pumped': non_pumped,
            'pumped': pumped,
            'junctions': junctions,
            'reservoirs': reservoirs,
            'tanks': tanks
        },
        'K_dimension': K
    }


def display_e_matrix(E, components):
    """Display matrix with complete flow labels"""
    labels = []

    # 1. Flow from all pipes
    for i in range(components['non_pumped']):
        labels.append(f"PipeFlow_{i + 1}")

    # 2. Flow from Pumped pipes
    for i in range(components['pumped']):
        labels.append(f"PumpedFlow_{i + 1}")

    # 3. Non-pumped pipes (2 labels per pipe)
    for i in range(components['non_pumped']):
        labels.append(f"Pipe_{i + 1}_L")
        labels.append(f"Pipe_{i + 1}_R")

    # 4. Junctions
    labels += [f"Junction_{i + 1}" for i in range(components['junctions'])]

    # 5. Reservoirs
    labels += [f"Reservoir_{i + 1}" for i in range(components['reservoirs'])]

    # 6. Tanks (last rows)
    labels += [f"Tank_{i + 1}" for i in range(components['tanks'])]

    # Verify label count matches matrix dimension
    assert len(labels) == len(E), f"Labels: {len(labels)} vs Matrix: {len(E)}"

    # Build matrix display
    matrix_str = f"Matrix Dimension: {len(E)}x{len(E[0])}\n\n"
    header = "Row Label".ljust(20) + " ".join(f"{label:<10}" for label in labels)
    matrix_str += header + "\n"

    for row_idx, row in enumerate(E):
        matrix_str += f"{labels[row_idx]:<20}"
        matrix_str += " ".join(f"{'[1]' if x else ' 0 '}" for x in row)
        matrix_str += "\n"

    return matrix_str
def main():
    st.title("Water Network Builder 🌊")

    # Initialize session state
    if 'nodes' not in st.session_state:
        st.session_state.nodes = []
    if 'pipes' not in st.session_state:
        st.session_state.pipes = []

    # Node creation form
    with st.expander("➕ Add New Node", expanded=True):
        with st.form("node_form"):
            node_id = st.text_input("Node ID")
            node_type = st.selectbox("Type", ["Junction", "Tank", "Reservoir"])
            attributes = {}

            if node_type == "Reservoir":
                attributes["elevation"] = st.number_input("Elevation (m)", min_value=0.0)
            elif node_type == "Tank":
                attributes["capacity"] = st.number_input("Capacity (m³)", min_value=0.0)

            if st.form_submit_button("Add Node"):
                if any(n['id'] == node_id for n in st.session_state.nodes):
                    st.error("Node ID must be unique!")
                else:
                    st.session_state.nodes.append({
                        'id': node_id,
                        'type': node_type.lower(),
                        **attributes
                    })
                    st.success("Node added successfully!")

    # Pipe creation form
    with st.expander("🔗 Add New Pipe"):
        with st.form("pipe_form"):
            col1, col2 = st.columns(2)
            with col1:
                start_node = st.selectbox("Start Node",
                                          [n['id'] for n in st.session_state.nodes],
                                          index=0)
            with col2:
                end_node = st.selectbox("End Node",
                                        [n['id'] for n in st.session_state.nodes],
                                        index=min(1, len(st.session_state.nodes) - 1))

            has_pump = st.checkbox("Contains Pump")
            pump_power = 0.0
            if has_pump:
                pump_power = st.number_input("Pump Power (kW)", min_value=0.1)

            length = st.number_input("Length (m)", min_value=0.1)
            diameter = st.number_input("Diameter (m)", min_value=0.01)

            if st.form_submit_button("Add Pipe"):
                # Validate pump between junctions
                start_type = next(n['type'] for n in st.session_state.nodes if n['id'] == start_node)
                end_type = next(n['type'] for n in st.session_state.nodes if n['id'] == end_node)

                if has_pump and (start_type != 'junction' or end_type != 'junction'):
                    st.error("Pumps can only be placed between two junctions!")
                elif start_node == end_node:
                    st.error("Start and end nodes cannot be the same!")
                else:
                    st.session_state.pipes.append({
                        'start': start_node,
                        'end': end_node,
                        'length': length,
                        'diameter': diameter,
                        'has_pump': has_pump,
                        'pump_power': pump_power if has_pump else None
                    })
                    st.success("Pipe added successfully!")

    # Visualization and Data Display
    st.subheader("Network Visualization")
    if st.session_state.nodes:
        visualize_graph()
    else:
        st.info("No nodes added yet. Add nodes to see visualization.")

    # Raw data display
    with st.expander("📁 View Raw Data"):
        st.write("Nodes:", st.session_state.nodes)
        st.write("Pipes:", st.session_state.pipes)

    with st.expander("🧮 Network Matrices"):
        if st.session_state.nodes and st.session_state.pipes:
            matrices = create_network_matrices(st.session_state.nodes, st.session_state.pipes)

            st.subheader("E Matrix Structure")
            st.write(f"Matrix Dimension (K x K): {matrices['K_dimension']} x {matrices['K_dimension']}")

            # Visualize E matrix pattern
            fig, ax = plt.subplots(figsize=(8, 8))
            ax.imshow(matrices['E_matrix'], cmap='binary')
            ax.set_title("E Matrix Pattern (1=active, 0=inactive)")
            st.pyplot(fig)

            st.write("Network Parameters:", matrices['components'])
            # st.write("First 10 rows of E matrix:")
            st.write(pd.DataFrame(matrices['E_matrix']))

    with st.expander("🧮 Network Matrices Detailed"):
        if st.session_state.nodes and st.session_state.pipes:
            matrices = create_network_matrices(st.session_state.nodes, st.session_state.pipes)

            st.subheader("Enhanced E Matrix Display")

            # Text-based display with labels
            st.text(display_e_matrix(matrices['E_matrix'], matrices['components']))

            # Color version for terminals (optional)
            st.code(display_e_matrix(matrices['E_matrix'], matrices['components']), language='ansi')

            # Simplified LaTeX version with labels
            latex_str = r"\begin{bmatrix}" + "\n"
            for row in matrices['E_matrix']:
                latex_str += " & ".join([r"\mathbf{1}" if x else "0" for x in row]) + r" \\" + "\n"
            latex_str += r"\end{bmatrix}"
            st.latex(latex_str)

    # # Optional: Add LaTeX rendering
    # with st.expander("View as Rendered LaTeX"):
    #     st.latex(display_e_matrix(matrices['E_matrix']))
    #
    #     # Add download option for large matrices
    #     st.download_button(
    #         label="Download E Matrix as Text",
    #         data="\n".join(["\t".join(map(str, row)) for row in matrices['E_matrix']]),
    #         file_name="E_matrix.txt"
    #     )


if __name__ == "__main__":
    main()