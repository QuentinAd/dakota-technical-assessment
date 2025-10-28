"""Synthetic data generation logic for enrichment data.

This module generates deterministic synthetic data based on location and period.
Uses hash-based generation to ensure:
1. Same inputs always produce same outputs (deterministic)
2. Different inputs produce different outputs
3. Values are realistic and within expected ranges
"""

import hashlib


def _hash_string(value: str) -> int:
    """Generate a consistent hash integer from a string.

    Args:
        value: String to hash

    Returns:
        Integer hash value
    """
    return int(hashlib.sha256(value.encode()).hexdigest(), 16)


def _hash_to_range(value: str, min_val: float, max_val: float) -> float:
    """Generate a float in a range based on string hash.

    Args:
        value: String to hash
        min_val: Minimum value
        max_val: Maximum value

    Returns:
        Float value in [min_val, max_val]
    """
    hash_int = _hash_string(value)
    # Normalize to [0, 1]
    normalized = (hash_int % 1000000) / 1000000
    # Scale to [min_val, max_val]
    return min_val + (normalized * (max_val - min_val))


def generate_temperature(location: str, period: str) -> float:
    """Generate synthetic temperature data.

    Temperature varies by location and time period.

    Args:
        location: Location code (e.g., 'US-CA')
        period: Time period (e.g., '2024-01-15')

    Returns:
        Temperature in Fahrenheit (realistic range: 0-100°F)
    """
    seed = f"{location}:{period}:temperature"
    # Generate temperature in realistic range (0-100°F for most US locations)
    return round(_hash_to_range(seed, 10.0, 95.0), 1)


def generate_population(location: str) -> int:
    """Generate synthetic population data.

    Population primarily varies by location (not time).

    Args:
        location: Location code (e.g., 'US-CA')

    Returns:
        Population estimate (realistic range: 500k-40M for US states)
    """
    seed = f"{location}:population"
    # Generate population in realistic range for US states
    return int(_hash_to_range(seed, 500000, 40000000))


def generate_gdp_per_capita(location: str, period: str) -> float:
    """Generate synthetic GDP per capita data.

    GDP varies by location and grows slowly over time.

    Args:
        location: Location code (e.g., 'US-CA')
        period: Time period (e.g., '2024-01-15')

    Returns:
        GDP per capita in USD (realistic range: $40k-$100k for US states)
    """
    seed = f"{location}:{period}:gdp"
    # Generate GDP in realistic range for US states
    return round(_hash_to_range(seed, 40000.0, 100000.0), 2)


def generate_industrial_activity_index(location: str, period: str) -> float:
    """Generate synthetic industrial activity index.

    Index measures industrial activity level (base 100).
    Varies by location and time period.

    Args:
        location: Location code (e.g., 'US-CA')
        period: Time period (e.g., '2024-01-15')

    Returns:
        Industrial activity index (range: 70-130, base 100)
    """
    seed = f"{location}:{period}:industrial"
    # Generate index around base 100 with variation
    return round(_hash_to_range(seed, 70.0, 130.0), 1)
