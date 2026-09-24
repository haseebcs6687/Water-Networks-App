import streamlit as st
import networkx as nx
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Circle


def visualize_graph():
    G = nx.Graph()

    # Add nodes with positions (you can modify this to include actual coordinates)
    for i, node in enumerate(st.session_state.nodes):
        G.add_node(node['id'], type=node['type'])

    # Add edges
    for pipe in st.session_state.pipes:
        G.add_edge(pipe['start'], pipe['end'], length=pipe['length'], diameter=pipe['diameter'])

    # Draw graph
    pos = nx.spring_layout(G, seed=42)
    fig, ax = plt.subplots(figsize=(8, 6))

    # Node colors based on type
    node_colors = {
        'junction': 'skyblue',
        'pump': 'limegreen',
        'reservoir': 'salmon'
    }

    for node_type in node_colors:
        nx.draw_networkx_nodes(G, pos,
                               nodelist=[n['id'] for n in st.session_state.nodes if n['type'] == node_type],
                               node_color=node_colors[node_type],
                               node_size=800,
                               ax=ax)

    nx.draw_networkx_edges(G, pos, width=1.5, ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=10, ax=ax)

    # Create legend
    legend_elements = [Circle(0, color=v, label=k.capitalize()) for k, v in node_colors.items()]
    ax.legend(handles=legend_elements, loc='upper right')

    plt.title("Water Network Graph")
    st.pyplot(fig)


def create_network_matrices(nodes, pipes):
    """Create matrix representations of the network"""
    node_ids = [n['id'] for n in nodes]
    node_index = {node_id: idx for idx, node_id in enumerate(node_ids)}
    num_nodes = len(nodes)
    num_pipes = len(pipes)

    matrices = {
        'node_index': node_index,
        'adjacency': [[0] * num_nodes for _ in range(num_nodes)],
        'incidence': [[0] * num_pipes for _ in range(num_nodes)],
        'length_matrix': [[0] * num_nodes for _ in range(num_nodes)],
        'diameter_matrix': [[0] * num_nodes for _ in range(num_nodes)],
        'pipe_attributes': []
    }

    for pipe_idx, pipe in enumerate(pipes):
        # Get node indices
        i = node_index[pipe['start']]
        j = node_index[pipe['end']]

        # Update adjacency matrix (undirected)
        matrices['adjacency'][i][j] += 1
        matrices['adjacency'][j][i] += 1

        # Update incidence matrix (directed)
        matrices['incidence'][i][pipe_idx] = -1  # Outgoing
        matrices['incidence'][j][pipe_idx] = 1  # Incoming

        # Update length/diameter matrices (sum values)
        matrices['length_matrix'][i][j] += pipe['length']
        matrices['length_matrix'][j][i] += pipe['length']
        matrices['diameter_matrix'][i][j] += pipe['diameter']
        matrices['diameter_matrix'][j][i] += pipe['diameter']

        # Store pipe attributes with node indices
        matrices['pipe_attributes'].append({
            'start_idx': i,
            'end_idx': j,
            'length': pipe['length'],
            'diameter': pipe['diameter']
        })

    return matrices

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
            node_type = st.selectbox("Type", ["Junction", "Pump", "Reservoir"])
            attributes = {}

            if node_type == "Reservoir":
                attributes["elevation"] = st.number_input("Elevation (m)", min_value=0.0)
            elif node_type == "Pump":
                attributes["power"] = st.number_input("Power (kW)", min_value=0.0)

            if st.form_submit_button("Add Node"):
                # Check for duplicate ID
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

            length = st.number_input("Length (m)", min_value=0.1)
            diameter = st.number_input("Diameter (m)", min_value=0.01)

            if st.form_submit_button("Add Pipe"):
                if start_node == end_node:
                    st.error("Start and end nodes cannot be the same!")
                else:
                    st.session_state.pipes.append({
                        'start': start_node,
                        'end': end_node,
                        'length': length,
                        'diameter': diameter
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
        col1, col2 = st.columns(2)
        with col1:
            st.write("Nodes:", st.session_state.nodes)
        with col2:
            st.write("Pipes:", st.session_state.pipes)

    # Add matrix visualization section
    with st.expander("🧮 Network Matrices"):
        if st.session_state.nodes and st.session_state.pipes:
            matrices = create_network_matrices(st.session_state.nodes, st.session_state.pipes)

            st.subheader("Node Index Mapping")
            st.write(matrices['node_index'])

            st.subheader("Adjacency Matrix (Connection Count)")
            df_adj = pd.DataFrame(
                matrices['adjacency'],
                index=matrices['node_index'].keys(),
                columns=matrices['node_index'].keys()
            )
            st.dataframe(df_adj)

            st.subheader("Incidence Matrix (Directed)")
            df_inc = pd.DataFrame(
                matrices['incidence'],
                index=matrices['node_index'].keys(),
                columns=[f"Pipe {i + 1}" for i in range(len(st.session_state.pipes))]
            )
            st.dataframe(df_inc)

            st.subheader("Length Matrix (Total Length Between Nodes)")
            df_len = pd.DataFrame(
                matrices['length_matrix'],
                index=matrices['node_index'].keys(),
                columns=matrices['node_index'].keys()
            )
            st.dataframe(df_len)

            st.subheader("Pipe Attributes List")
            st.write(matrices['pipe_attributes'])

        else:
            st.info("Add nodes and pipes to generate matrices")



if __name__ == "__main__":
    main()