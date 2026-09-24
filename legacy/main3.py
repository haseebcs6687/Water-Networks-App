import streamlit as st
import networkx as nx
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

# Initialize session state variables
if 'nodes' not in st.session_state:
    st.session_state.nodes = []
    st.session_state.pipes = []  # Critical missing line
    st.session_state.junction_count = 0
    st.session_state.tank_count = 0
    st.session_state.reservoir_count = 0
    st.session_state.pipe_count = 0

def generate_node_id(node_type):
    """Generate standardized node IDs"""
    if node_type == 'junction':
        st.session_state.junction_count += 1
        return f"J{st.session_state.junction_count}"
    elif node_type == 'tank':
        st.session_state.tank_count += 1
        return f"T{st.session_state.tank_count}"
    elif node_type == 'reservoir':
        st.session_state.reservoir_count += 1
        return f"R{st.session_state.reservoir_count}"
    return ""


def generate_pipe_id():
    """Generate standardized pipe IDs"""
    st.session_state.pipe_count += 1
    return f"P{st.session_state.pipe_count}"


def display_matrix(matrix, components, title):
    """Display matrix with proper labels"""
    labels = []

    # 1. All pipe flows
    labels += [f"{pid}_Flow" for pid in components['all_pipes']]

    # 2. Non-pumped L/R
    labels += [f"{pid}_L" for pid in components['non_pumped']]
    labels += [f"{pid}_R" for pid in components['non_pumped']]

    # 3. Junctions
    labels += components['junctions']

    # 4. Reservoirs
    labels += components['reservoirs']

    # 5. Tanks
    labels += components['tanks']

    # Build matrix display
    matrix_str = f"{title} ({components['K']}x{components['K']})\n\n"
    header = " " * 20 + " ".join(f"{label:^10}" for label in labels)
    matrix_str += header + "\n"

    for row_idx, row in enumerate(matrix):
        label = labels[row_idx] if row_idx < len(labels) else f"Row{row_idx + 1}"
        matrix_str += f"{label:<20}"
        matrix_str += " ".join(f"{str(cell):^10}" for cell in row)
        matrix_str += "\n"

    return matrix_str

def create_network_matrices():
    """Create matrices with correct flow-first ordering"""
    # Get components
    all_pipes = st.session_state.pipes
    non_pumped = [p for p in all_pipes if not p['has_pump']]
    pumped = [p for p in all_pipes if p['has_pump']]
    junctions = [n['id'] for n in st.session_state.nodes if n['type'] == 'junction']
    reservoirs = [n['id'] for n in st.session_state.nodes if n['type'] == 'reservoir']
    tanks = [n['id'] for n in st.session_state.nodes if n['type'] == 'tank']

    # Create index mappings
    junction_idx = {jid: idx for idx, jid in enumerate(junctions)}
    pipe_idx = {p['id']: idx for idx, p in enumerate(all_pipes)}

    # Calculate matrix dimension
    K = (len(all_pipes) +  # All pipe flows
         2 * len(non_pumped) +  # Non-pumped L/R
         len(junctions) +
         len(reservoirs) +
         len(tanks))

    # Initialize matrices
    E =[[0] * K for _ in range(K)]
    A = [['0'] * K for _ in range(K)]

    # Populate E matrix diagonal
    for i in range(len(all_pipes) + 2 * len(non_pumped)):
        E[i][i] = 1
    for i in range(K - len(tanks), K):
        E[i][i] = 1

    # Populate A matrix coefficients
    for pipe in non_pumped:
        p_idx = pipe_idx[pipe['id']]

    # Flow equation row
    flow_row = p_idx
    A[flow_row][flow_row] = '1'  # Self-flow

    # Left side equation
    left_row = len(all_pipes) + 2 * p_idx
    if pipe['start'] in junction_idx:
        j_col = len(all_pipes) + 2 * len(non_pumped) + junction_idx[pipe['start']]
        A[left_row][j_col] = '1'
        A[left_row][left_row] = '-1'

    # Right side equation
    right_row = len(all_pipes) + 2 * p_idx + 1
    if pipe['end'] in junction_idx:
        j_col = len(all_pipes) + 2 * len(non_pumped) + junction_idx[pipe['end']]
        A[right_row][j_col] = '1'
        A[right_row][right_row] = '-1'

    # Pumped pipes (flow only)
    for p_idx, pipe in enumerate(pumped, start=len(non_pumped)):
        flow_row = p_idx
    A[flow_row][flow_row] = '1'

    return {
        'E_matrix': E,
        'A_matrix': A,
        'components': {
            'all_pipes': [p['id'] for p in all_pipes],
            'non_pumped': [p['id'] for p in non_pumped],
            'pumped_pipes': [p['id'] for p in pumped],
            'junctions': junctions,
            'reservoirs': reservoirs,
            'tanks': tanks,
            'K': K
        }
    }


def display_matrix(matrix, components, title):
    """Display matrix with proper labels"""
    labels = []
    # Pipe labels (P1_L, P1_R, ...)
    for pid in components['all_pipes']:
        labels.append(f"{pid}_L")
        labels.append(f"{pid}_R")

    # Pumped pipes
    for pid in components['pumped_pipes']:
        labels.append(f"{pid}_Flow")

    # Junctions
    labels += components['junctions']

    # Reservoirs
    labels += components['reservoirs']

    # Tanks
    labels += components['tanks']

    # Create display string
    matrix_str = f"{title} ({components['K']}x{components['K']})\n\n"
    header = " " * 20 + " ".join(f"{label:^8}" for label in labels)
    matrix_str += header + "\n"

    for row_idx, row in enumerate(matrix):
        label = labels[row_idx] if row_idx < len(labels) else f"Row{row_idx + 1}"
        matrix_str += f"{label:<20}"
        if isinstance(row[0], str):
            matrix_str += " ".join(f"{cell:^8}" for cell in row)
        else:
            matrix_str += " ".join(f"{'1' if cell else '0':^8}" for cell in row)
        matrix_str += "\n"

    return matrix_str


def visualize_network():
    """Create network visualization"""
    G = nx.Graph()
    node_colors = {
        'junction': 'skyblue',
        'tank': 'gold',
        'reservoir': 'salmon'
    }

    # Add nodes
    for node in st.session_state.nodes:
        G.add_node(node['id'], type=node['type'])

    # Add edges
    for pipe in st.session_state.pipes:
        edge_attrs = {
            'label': pipe['id'],
            'style': 'dashed' if pipe['has_pump'] else 'solid'
        }
        if pipe['has_pump']:
            edge_attrs['label'] += f"\n{pipe['pump_power']}kW"
        G.add_edge(pipe['start'], pipe['end'], **edge_attrs)

    # Draw graph
    pos = nx.spring_layout(G, seed=42)
    fig, ax = plt.subplots(figsize=(10, 8))

    # Draw nodes
    for node_type, color in node_colors.items():
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=[n['id'] for n in st.session_state.nodes if n['type'] == node_type],
            node_color=color,
            node_size=1000,
            ax=ax
        )

    # Draw edges
    for edge in G.edges(data=True):
        style = edge[2].get('style', 'solid')
        nx.draw_networkx_edges(
            G, pos,
            edgelist=[(edge[0], edge[1])],
            style=style,
            width=2,
            ax=ax
        )
        edge_label = edge[2].get('label', '')
        nx.draw_networkx_edge_labels(
            G, pos,
            edge_labels={(edge[0], edge[1]): edge_label},
            ax=ax
        )

    # Labels and legend
    nx.draw_networkx_labels(G, pos, ax=ax)
    legend_elements = [
        Circle(0, color='skyblue', label='Junction'),
        Circle(0, color='gold', label='Tank'),
        Circle(0, color='salmon', label='Reservoir'),
        plt.Line2D([0], [0], color='black', linestyle='-', label='Pipe'),
        plt.Line2D([0], [0], color='black', linestyle='--', label='Pump')
    ]
    ax.legend(handles=legend_elements, loc='upper right')
    plt.title("Water Network Diagram")
    st.pyplot(fig)


# Streamlit UI
def main():
    st.title("Smart Water Network Builder 💧")


    # Node creation
    with st.expander("🏗️ Add Node", expanded=True):
        node_type = st.selectbox("Node Type", ["Junction", "Tank", "Reservoir"])
        if st.button("Add Node"):
            new_node = {
                'id': generate_node_id(node_type.lower()),
                'type': node_type.lower()
            }
            if node_type.lower() == 'tank':
                new_node['capacity'] = 1000  # Default capacity
            elif node_type.lower() == 'reservoir':
                new_node['elevation'] = 50  # Default elevation

            st.session_state.nodes.append(new_node)
            st.success(f"Added {new_node['id']} ({node_type})")

    # Pipe creation
    with st.expander("🕳️ Add Pipe"):
        node_ids = [n['id'] for n in st.session_state.nodes]
        col1, col2 = st.columns(2)
        with col1:
            start_node = st.selectbox("Start Node", node_ids)
        with col2:
            end_node = st.selectbox("End Node", node_ids)

        has_pump = st.checkbox("Contains Pump")
        pump_power = st.number_input("Pump Power (kW)", min_value=0.0) if has_pump else 0.0

        if st.button("Add Pipe"):
            if start_node == end_node:
                st.error("Cannot connect a node to itself!")
            else:
                new_pipe = {
                    'id': generate_pipe_id(),
                    'start': start_node,
                    'end': end_node,
                    'has_pump': has_pump,
                    'pump_power': pump_power
                }
                st.session_state.pipes.append(new_pipe)
                st.success(f"Added {new_pipe['id']} between {start_node} and {end_node}")

    # Network visualization
    st.subheader("Network Visualization")
    if st.session_state.nodes:
        visualize_network()
    else:
        st.info("No nodes added yet")

    # Matrix display
    if st.session_state.nodes and st.session_state.pipes:
        matrices = create_network_matrices()

        with st.expander("📊 System Matrices"):
            st.subheader("E Matrix (Diagonal Structure)")
            st.text(display_matrix(matrices['E_matrix'], matrices['components'], "E Matrix"))

            st.subheader("A Matrix (Flow Coefficients)")
            st.text(display_matrix(matrices['A_matrix'], matrices['components'], "A Matrix"))

            st.subheader("Matrix Interpretation")
            st.markdown("""
            - **P1_L, P1_R**: Pipe endpoints (Left/Right)
            - **J#**: Junctions
            - **T#**: Tanks
            - **R#**: Reservoirs
            - **c#**: Flow coefficients
            - **-c#**: Negative flow coefficients
            """)

    # Raw data
    with st.expander("📁 Raw Data"):
        st.write("Nodes:", st.session_state.nodes)
        st.write("Pipes:", st.session_state.pipes)


if __name__ == "__main__":
    main()