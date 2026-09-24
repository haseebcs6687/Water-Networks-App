"""Sample networks for testing and GUI demo presets."""

from core.models import Network


def example_paper_network() -> Network:
    """Create a valid, regular paper-inspired network with 1 reservoir, 1 tank, 4 junctions, 1 pump, 8 pipes."""
    net = Network()
    net.add_node("reservoir", id="R1", elevation=50.0)
    net.add_node("tank", id="T1", capacity=1000.0)
    net.add_node("junction", id="J1")
    net.add_node("junction", id="J2")
    net.add_node("junction", id="J3")
    net.add_node("junction", id="J4")

    net.add_pipe("R1", "J1", id="P1")
    net.add_pipe("J1", "J2", id="P2")
    net.add_pipe("J2", "J3", id="P3", has_pump=True, pump_power=15.0)
    net.add_pipe("J3", "J4", id="P4")
    net.add_pipe("J4", "T1", id="P5")
    net.add_pipe("J1", "J3", id="P6")
    net.add_pipe("J2", "J4", id="P7")
    net.add_pipe("J3", "T1", id="P8")

    return net


def example_broken_network() -> Network:
    """Create a broken network containing an unsupplied island and a pump cycle."""
    net = Network()
    net.add_node("reservoir", id="R1")
    net.add_node("junction", id="J1")
    net.add_node("junction", id="J2")
    net.add_node("junction", id="J3")
    net.add_node("junction", id="J4")
    net.add_node("junction", id="J5")

    # Supply chain with pump loop
    net.add_pipe("R1", "J1", id="P1")
    net.add_pipe("J1", "J2", id="P2", has_pump=True, pump_power=10.0)
    net.add_pipe("J2", "J3", id="P3", has_pump=True, pump_power=10.0)
    net.add_pipe("J3", "J1", id="P4", has_pump=True, pump_power=10.0)

    # Disconnected island without supply
    net.add_pipe("J4", "J5", id="P5")

    return net
