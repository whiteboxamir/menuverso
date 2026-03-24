#!/usr/bin/env python3
"""
Menuverso Metro Station Mapper — Assigns nearest Barcelona metro station to geocoded restaurants.
Uses a comprehensive lookup table of all Barcelona metro stations with their coordinates.
"""

import json
import math

INPUT = "restaurants.json"

# Barcelona Metro Stations: (name, line(s), lat, lng)
METRO_STATIONS = [
    # L1 (Red)
    ("Hospital de Bellvitge", "L1", 41.3469, 2.0889),
    ("Bellvitge", "L1", 41.3495, 2.0938),
    ("Av. Carrilet", "L1", 41.3577, 2.1001),
    ("Rambla Just Oliveras", "L1", 41.3599, 2.1082),
    ("Can Serra", "L1", 41.3632, 2.1117),
    ("Florida", "L1", 41.3658, 2.1201),
    ("Torrassa", "L1", 41.3680, 2.1248),
    ("Santa Eulàlia", "L1", 41.3746, 2.1348),
    ("Mercat Nou", "L1", 41.3745, 2.1411),
    ("Plaça de Sants", "L1", 41.3790, 2.1380),
    ("Hostafrancs", "L1", 41.3766, 2.1458),
    ("Espanya", "L1/L3", 41.3752, 2.1487),
    ("Rocafort", "L1", 41.3782, 2.1502),
    ("Urgell", "L1", 41.3869, 2.1560),
    ("Universitat", "L1/L2", 41.3879, 2.1645),
    ("Catalunya", "L1/L3", 41.3872, 2.1699),
    ("Urquinaona", "L1/L4", 41.3895, 2.1722),
    ("Arc de Triomf", "L1", 41.3910, 2.1808),
    ("Marina", "L1", 41.3975, 2.1881),
    ("Glòries", "L1", 41.4015, 2.1878),
    ("Clot", "L1/L2", 41.4102, 2.1876),
    ("Navas", "L1", 41.4072, 2.1814),
    ("La Sagrera", "L1/L5/L9/L10", 41.4239, 2.1878),
    ("Fabra i Puig", "L1", 41.4290, 2.1830),
    ("Sant Andreu", "L1", 41.4350, 2.1892),
    ("Torras i Bages", "L1", 41.4381, 2.1926),
    ("Trinitat Vella", "L1", 41.4452, 2.1912),
    ("Baró de Viver", "L1", 41.4430, 2.1989),
    ("Santa Coloma", "L1", 41.4485, 2.2067),
    ("Fondo", "L1", 41.4513, 2.2148),

    # L2 (Purple)
    ("Paral·lel", "L2/L3", 41.3753, 2.1695),
    ("Sant Antoni", "L2", 41.3801, 2.1639),
    ("Passeig de Gràcia", "L2/L3/L4", 41.3918, 2.1650),
    ("Tetuan", "L2", 41.3945, 2.1746),
    ("Monumental", "L2", 41.3981, 2.1810),
    ("Sagrada Família", "L2/L5", 41.4034, 2.1742),
    ("Encants", "L2", 41.4044, 2.1822),
    ("Sant Martí", "L2", 41.4182, 2.1891),
    ("La Pau", "L2/L4", 41.4209, 2.1966),
    ("Verneda", "L2", 41.4213, 2.2020),
    ("Artigues/Sant Adrià", "L2", 41.4215, 2.2110),
    ("Sant Roc", "L2", 41.4330, 2.2260),
    ("Gorg", "L2/L10", 41.4395, 2.2285),
    ("Pep Ventura", "L2", 41.4449, 2.2286),
    ("Badalona Pompeu Fabra", "L2", 41.4490, 2.2360),

    # L3 (Green)
    ("Zona Universitària", "L3", 41.3857, 2.1134),
    ("Palau Reial", "L3", 41.3876, 2.1177),
    ("Maria Cristina", "L3", 41.3922, 2.1282),
    ("Les Corts", "L3", 41.3867, 2.1287),
    ("Plaça del Centre", "L3", 41.3834, 2.1343),
    ("Sants Estació", "L3/L5", 41.3797, 2.1394),
    ("Tarragona", "L3", 41.3759, 2.1413),
    ("Poble Sec", "L3", 41.3722, 2.1575),
    ("Drassanes", "L3", 41.3738, 2.1738),
    ("Liceu", "L3", 41.3805, 2.1733),
    ("Fontana", "L3", 41.4030, 2.1569),
    ("Lesseps", "L3", 41.4033, 2.1488),
    ("Vallcarca", "L3", 41.4060, 2.1429),
    ("Penitents", "L3", 41.4087, 2.1368),
    ("Vall d'Hebron", "L3/L5", 41.4275, 2.1453),
    ("Montbau", "L3", 41.4322, 2.1435),
    ("Mundet", "L3", 41.4370, 2.1448),
    ("Valldaura", "L3", 41.4418, 2.1512),
    ("Canyelles", "L3", 41.4437, 2.1580),
    ("Roquetes", "L3", 41.4497, 2.1640),
    ("Trinitat Nova", "L3/L4/L11", 41.4508, 2.1760),

    # L4 (Yellow)
    ("Trinitat Nova", "L3/L4", 41.4508, 2.1760),
    ("Via Júlia", "L4", 41.4401, 2.1748),
    ("Llucmajor", "L4", 41.4360, 2.1745),
    ("Maragall", "L4/L5", 41.4309, 2.1704),
    ("Guinardó/Hospital de Sant Pau", "L4", 41.4209, 2.1687),
    ("Alfons X", "L4", 41.4136, 2.1699),
    ("Joanic", "L4", 41.4045, 2.1608),
    ("Verdaguer", "L4/L5", 41.3953, 2.1672),
    ("Girona", "L4", 41.3933, 2.1685),
    ("Jaume I", "L4", 41.3841, 2.1764),
    ("Barceloneta", "L4", 41.3806, 2.1892),
    ("Ciutadella/Vila Olímpica", "L4", 41.3896, 2.1973),
    ("Bogatell", "L4", 41.3982, 2.2031),
    ("Llacuna", "L4", 41.3989, 2.1941),
    ("Poblenou", "L4", 41.4031, 2.2015),
    ("Selva de Mar", "L4", 41.4095, 2.2100),
    ("El Maresme/Fòrum", "L4", 41.4109, 2.2190),

    # L5 (Blue)
    ("Cornellà Centre", "L5", 41.3537, 2.1077),
    ("Gavarra", "L5", 41.3581, 2.1210),
    ("Sant Ildefons", "L5", 41.3612, 2.1290),
    ("Can Boixeres", "L5", 41.3660, 2.1310),
    ("Can Vidalet", "L5", 41.3691, 2.1350),
    ("Pubilla Cases", "L5", 41.3693, 2.1257),
    ("Collblanc", "L5", 41.3757, 2.1294),
    ("Badal", "L5", 41.3749, 2.1356),
    ("Plaça de Sants", "L5", 41.3790, 2.1380),
    ("Entença", "L5", 41.3803, 2.1479),
    ("Hospital Clínic", "L5", 41.3908, 2.1521),
    ("Diagonal", "L3/L5", 41.3945, 2.1530),
    ("Verdaguer", "L4/L5", 41.3953, 2.1672),
    ("Sagrada Família", "L2/L5", 41.4034, 2.1742),
    ("Sant Pau/Dos de Maig", "L5", 41.4104, 2.1719),
    ("Camp de l'Arpa", "L5", 41.4136, 2.1791),
    ("El Congrés", "L5", 41.4238, 2.1812),
    ("Horta", "L5", 41.4322, 2.1610),
    ("El Carmel", "L5", 41.4276, 2.1541),
    ("El Coll/La Teixonera", "L5", 41.4238, 2.1511),

    # L9/L10 South
    ("Aeroport T1", "L9S", 41.2868, 2.0740),
    ("Aeroport T2", "L9S", 41.2979, 2.0785),
    ("Fira", "L9S/L10S", 41.3560, 2.1264),
    ("Europa/Fira", "L9S/L10S", 41.3619, 2.1337),
    ("Zona Franca", "L10S", 41.3582, 2.1439),
    ("Foc Cisell", "L10S", 41.3640, 2.1558),

    # Additional central
    ("Diagonal", "L3/L5", 41.3945, 2.1530),
];

def haversine(lat1, lng1, lat2, lng2):
    """Distance in meters between two points."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_nearest_station(lat, lng):
    """Find the nearest metro station and return (name, line, distance_m)."""
    best = None
    best_dist = float('inf')
    for name, line, slat, slng in METRO_STATIONS:
        d = haversine(lat, lng, slat, slng)
        if d < best_dist:
            best_dist = d
            best = (name, line, d)
    return best


def main():
    with open(INPUT) as f:
        restaurants = json.load(f)

    total = len(restaurants)
    mapped = 0
    skipped = 0

    for r in restaurants:
        coords = r.get("coordinates", {})
        lat = coords.get("lat")
        lng = coords.get("lng")
        if lat and lng:
            name, line, dist = find_nearest_station(lat, lng)
            r["metro_station"] = f"{name} ({line})"
            mapped += 1
        else:
            skipped += 1

    # Save
    with open(INPUT, "w") as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)

    with open("restaurants_data.js", "w") as f:
        f.write("var RESTAURANT_DATA = ")
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
        f.write(";\n")

    print(f"🚇 Mapped {mapped}/{total} restaurants to nearest metro station")
    print(f"   Skipped {skipped} (no coordinates)")

    # Show distribution of top stations
    from collections import Counter
    stations = Counter(r.get("metro_station", "") for r in restaurants if r.get("metro_station"))
    print(f"\n📊 Top 15 metro stations:")
    for station, count in stations.most_common(15):
        bar = "█" * (count // 2)
        print(f"   {station:35s} {count:3d}  {bar}")


if __name__ == "__main__":
    main()
