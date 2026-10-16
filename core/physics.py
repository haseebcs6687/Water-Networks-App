"""core/physics.py – Physical constants, fluid properties, and calculation settings.

Classes
-------
PhysicsSettings
    Dataclass holding gravitational acceleration, kinematic viscosity,
    and friction calculation parameters.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PhysicsSettings:
    """Physical constants and calculation settings.

    Parameters
    ----------
    g : float
        Gravitational acceleration in m/s^2. EPANET defines standard gravity
        as 32.2 ft/s^2, which in SI metric units is 32.2 * 0.3048 = 9.81456 m/s^2.
        Using this exact value ensures bitwise agreement with EPANET and the
        MATLAB reference.
    nu : float
        Kinematic viscosity of water at 20°C in m^2/s (1.0219e-6).
    friction_mode : str
        Friction formulation: 'constant' or 'darcy_weisbach' (default 'constant').
        Only 'constant' is supported in this task; 'darcy_weisbach' raises
        NotImplementedError with a clear explanation.
    friction_factor : float
        Darcy friction factor (dimensionless) used when friction_mode is
        'constant' (default 0.02).
    """

    g: float = 32.2 * 0.3048
    nu: float = 1.0219e-6
    friction_mode: str = "constant"
    friction_factor: float = 0.02

    def __post_init__(self) -> None:
        if self.friction_mode not in {"constant", "darcy_weisbach"}:
            raise ValueError(
                f"Unknown friction_mode: {self.friction_mode!r}. "
                "Must be 'constant' or 'darcy_weisbach'."
            )
        if self.friction_mode == "darcy_weisbach":
            raise NotImplementedError(
                "Darcy-Weisbach friction mode is not yet implemented (planned for a later task); "
                "only 'constant' is supported in this release."
            )
        if self.g <= 0:
            raise ValueError(f"g must be positive, got {self.g}")
        if self.nu <= 0:
            raise ValueError(f"nu must be positive, got {self.nu}")
        if self.friction_factor <= 0:
            raise ValueError(f"friction_factor must be positive, got {self.friction_factor}")
