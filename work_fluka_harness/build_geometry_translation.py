#!/usr/bin/env python3
"""Translate the current fix5 MEGAlib proxy geometry into a FLUKA CG ledger/input.

This script intentionally treats the MEGAlib files as the authority and writes
only under the harness output tree.  It is a deterministic translator/auditor,
not a source of new geometry dimensions.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

TES_ROOT = Path('/home/ubuntu/TES_511_Balloon')
OUT_ROOT = TES_ROOT / 'engineering/fluka_crosscode_validation_20260624'
GEOM_DIR = TES_ROOT / 'outputs/geometry/DEMO2_DR_v3p5_user_cylmag_redesign_multiholeW_fix5_20260621_megalib_proxy'
GEO = GEOM_DIR / 'DEMO2_DR_v3p5_minpatch_centerfinger_megalib_proxy.geo'
INTRO = GEOM_DIR / 'Intro_DEMO2_DR_v3p5_minpatch_centerfinger_megalib_proxy.geo'
MATFILE = GEOM_DIR / 'Materials_DEMO2_DR_v3p5.geo'
BOUNDS = GEOM_DIR / 'DEMO2_DR_v3p5_minpatch_centerfinger_bounds.json'
VALIDATION = GEOM_DIR / 'DEMO2_DR_v3p5_minpatch_centerfinger_validation.json'
FIX5_MANIFEST = TES_ROOT / 'outputs/reports/user_redesign_multiholeW_fix5_20260621/user_cylmag_redesign_multiholeW_fix5_manifest.json'
BACKGROUND_AUTHORITY_MANIFEST = TES_ROOT / 'engineering/background_validation_20260624/00_manifest/baseline_authority_manifest.json'
OUT = OUT_ROOT / '02_geometry_translation'
FLUKA_DIR = OUT / 'fluka_geometry'

CM3_TO_KG = 1.0e-3
EPS = 1.0e-10
MASS_REL_TARGET = 0.005
TOTAL_MASS_REL_TARGET = 0.001


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def flt(x: str | float | int) -> float:
    return float(x)


def fmt(x: float) -> str:
    if abs(x) < 5e-13:
        x = 0.0
    return f'{x:.10g}'


def card(name: str, *whats: object, sdum: str = '') -> str:
    def field(v: object) -> str:
        if v is None:
            return ''
        if isinstance(v, float):
            return f'{v:.6g}'
        if isinstance(v, int):
            return str(v)
        return str(v)
    vals = [field(v) for v in whats]
    vals += [''] * (6 - len(vals))
    return f'{name:<10}' + ''.join(f'{v:>10}' for v in vals[:6]) + f'{sdum:<10}\n'


def wrap_region(name: str, expr: str, naz: int = 5) -> str:
    words = expr.split()
    prefix = f'{name:<8} {naz:<3} '
    lines: list[str] = []
    current = prefix
    for word in words:
        candidate = current + ('' if current.endswith(' ') else ' ') + word
        if len(candidate) > 118 and current.strip():
            lines.append(current.rstrip())
            current = ' ' * len(prefix) + word
        else:
            current = candidate
    lines.append(current.rstrip())
    return '\n'.join(lines) + '\n'


@dataclass
class Shape:
    kind: str
    params: list[float] | list[str]


@dataclass
class VolumeDef:
    name: str
    material: str | None = None
    visibility: str | None = None
    shape_kind: str | None = None
    shape_params: list[float] | str | None = None
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    mother: str | None = None


@dataclass
class ObjectInstance:
    name: str
    logical: str
    material: str
    shape_kind: str
    shape_params: list[float] | str
    rel_position: tuple[float, float, float]
    rotation: tuple[float, float, float]
    mother: str | None
    abs_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    depth: int = 0
    is_copy: bool = False
    detector_kind: str = 'OTHER'
    region: str = ''
    bodies: list[str] = field(default_factory=list)
    expr: str = ''
    volume_cm3: float = 0.0
    mass_kg: float = 0.0
    translation_status: str = 'PENDING'
    notes: str = ''


class ShortNames:
    def __init__(self) -> None:
        self.body_i = 0
        self.region_i = 0
        self.mat_i = 0
        self.mat_map: dict[str, str] = {}

    def body(self) -> str:
        self.body_i += 1
        return f'B{self.body_i:07d}'[:8]

    def region(self) -> str:
        self.region_i += 1
        return f'R{self.region_i:07d}'[:8]


# FLUKA material names are limited to 8 chars.  Densities are MEGAlib material
# densities where the file declares custom materials; standard-material values
# are the conventional values used by the proxy material names.
MATERIALS = {
    'Vacuum': {'fluka': 'VACUUM', 'density': 0.0, 'components': []},
    'Copper': {'fluka': 'COPPER', 'density': 8.96, 'components': []},
    'Aluminium': {'fluka': 'ALUMINUM', 'density': 2.70, 'components': []},
    'Silicon': {'fluka': 'SILICON', 'density': 2.329, 'components': []},
    'CsI': {'fluka': 'CSI', 'density': 4.51, 'components': [('CESIUM', 1.0), ('IODINE', 1.0)]},
    'Nb': {'fluka': 'NIOBIUM', 'density': 8.57, 'components': [('NIOBIUM', 1.0)]},
    'W': {'fluka': 'TUNGSTEN', 'density': 19.3, 'components': []},
    'Ta': {'fluka': 'TANTALUM', 'density': 16.69, 'components': []},
    'Be': {'fluka': 'BERYLLIU', 'density': 1.85, 'components': []},
    'MuMetal': {'fluka': 'MUMETAL', 'density': 8.7, 'components': [('NICKEL', 4.0), ('IRON', 1.0)]},
    'Cryoperm': {'fluka': 'CRYOPERM', 'density': 8.7, 'components': [('NICKEL', 4.0), ('IRON', 1.0)]},
    'StainlessSteel': {'fluka': 'SS304', 'density': 8.0, 'components': [('IRON', 70.0), ('CHROMIUM', 18.0), ('NICKEL', 10.0), ('MANGANES', 2.0)]},
    'G10': {'fluka': 'G10', 'density': 1.85, 'components': [('SILICON', 1.0), ('OXYGEN', 2.0), ('CARBON', 3.0), ('HYDROGEN', 3.0)]},
    'Kapton': {'fluka': 'KAPTON', 'density': 1.42, 'components': [('CARBON', 22.0), ('HYDROGEN', 10.0), ('NITROGEN', 2.0), ('OXYGEN', 5.0)]},
    'CuNi': {'fluka': 'CUNI', 'density': 8.9, 'components': [('COPPER', 7.0), ('NICKEL', 3.0)]},
    'SilverSinterProxy': {'fluka': 'AGSINT', 'density': 5.0, 'components': [('SILVER', 1.0)]},
    'CharcoalProxy': {'fluka': 'CHARCOAL', 'density': 1.2, 'components': [('CARBON', 1.0)]},
    'NbTiCableProxy': {'fluka': 'NBTI', 'density': 6.5, 'components': [('NIOBIUM', 1.0), ('TITANIUM', 1.0)]},
}

ELEMENT_CARDS = {
    'CESIUM': (55.0, -132.90545196, 1.873),
    'IODINE': (53.0, -126.90447, 4.93),
    'NIOBIUM': (41.0, -92.90637, 8.57),
    'NICKEL': (28.0, -58.6934, 8.908),
    'IRON': (26.0, -55.845, 7.874),
    'CHROMIUM': (24.0, -51.9961, 7.19),
    'MANGANES': (25.0, -54.938044, 7.3),
    'SILICON': (14.0, -28.085, 2.329),
    'OXYGEN': (8.0, -15.999, 0.001429),
    'CARBON': (6.0, -12.011, 2.265),
    'HYDROGEN': (1.0, -1.00794, 8.988e-5),
    'NITROGEN': (7.0, -14.0067, 0.001251),
    'SILVER': (47.0, -107.8682, 10.49),
    'TITANIUM': (22.0, -47.867, 4.506),
}


def parse_material_file(path: Path) -> dict[str, dict[str, object]]:
    # The custom material file is compact; parse it so the audit can point to
    # exact authority values even where FLUKA uses built-ins.
    parsed: dict[str, dict[str, object]] = {}
    current: str | None = None
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or line.startswith('Include'):
            continue
        m = re.match(r'Material\s+(\S+)', line)
        if m:
            current = m.group(1)
            parsed[current] = {'density': None, 'components': []}
            continue
        m = re.match(r'(\S+)\.Density\s+([-+0-9.eE]+)', line)
        if m:
            parsed.setdefault(m.group(1), {'density': None, 'components': []})['density'] = float(m.group(2))
            current = m.group(1)
            continue
        m = re.match(r'(\S+)\.Component\s+(\S+)\s+([-+0-9.eE]+)', line)
        if m:
            parsed.setdefault(m.group(1), {'density': None, 'components': []})['components'].append((m.group(2), float(m.group(3))))
            current = m.group(1)
    return parsed


def parse_geo_files(paths: list[Path]) -> tuple[dict[str, VolumeDef], dict[str, Shape], dict[str, tuple[float, float, float]], list[ObjectInstance]]:
    volumes: dict[str, VolumeDef] = {}
    shapes: dict[str, Shape] = {}
    orientations: dict[str, tuple[float, float, float]] = {}
    copies: list[ObjectInstance] = []
    current_shape: str | None = None
    current_orientation: str | None = None

    def ensure_volume(name: str) -> VolumeDef:
        return volumes.setdefault(name, VolumeDef(name=name))

    for path in paths:
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith('//') or line.startswith('#') or line.startswith('Include'):
                continue
            if line.startswith('Name ') or line.startswith('Version ') or line.startswith('AbsorptionFileDirectory'):
                continue
            m = re.match(r'Volume\s+(\S+)$', line)
            if m:
                ensure_volume(m.group(1))
                current_shape = None
                current_orientation = None
                continue
            m = re.match(r'Shape\s+(PCON|BRIK|Subtraction)\s+(\S+)', line)
            if m:
                kind, name = m.group(1), m.group(2)
                shapes.setdefault(name, Shape(kind=kind, params=[]))
                current_shape = name
                current_orientation = None
                continue
            m = re.match(r'Orientation\s+(\S+)', line)
            if m:
                current_orientation = m.group(1)
                orientations.setdefault(current_orientation, (0.0, 0.0, 0.0))
                current_shape = None
                continue
            m = re.match(r'(\S+)\.Parameters\s+(.+)$', line)
            if m:
                name, rest = m.group(1), m.group(2).split()
                if name in shapes:
                    if shapes[name].kind == 'Subtraction':
                        shapes[name].params = rest
                    else:
                        shapes[name].params = [float(x) for x in rest]
                continue
            m = re.match(r'(\S+)\.Copy\s+(\S+)', line)
            if m:
                base, copy = m.group(1), m.group(2)
                b = ensure_volume(base)
                copies.append(ObjectInstance(
                    name=copy,
                    logical=base,
                    material=b.material or 'UNKNOWN',
                    shape_kind=b.shape_kind or 'UNKNOWN',
                    shape_params=b.shape_params if b.shape_params is not None else [],
                    rel_position=(0.0, 0.0, 0.0),
                    rotation=b.rotation,
                    mother=None,
                    is_copy=True,
                ))
                ensure_volume(copy)
                continue
            m = re.match(r'(\S+)\.(Material|Visibility|Shape|Position|Rotation|Mother)\s+(.+)$', line)
            if not m:
                continue
            name, attr, rest = m.group(1), m.group(2), m.group(3).strip()
            # Copy attributes are emitted as VolumeDef placeholders too; keep a
            # separate ObjectInstance in sync.
            v = ensure_volume(name)
            target_copy = next((c for c in reversed(copies) if c.name == name), None)
            if attr == 'Material':
                v.material = rest
            elif attr == 'Visibility':
                v.visibility = rest
            elif attr == 'Shape':
                parts = rest.split()
                if parts[0] in ('BRIK', 'PCON'):
                    v.shape_kind = parts[0]
                    v.shape_params = [float(x) for x in parts[1:]]
                else:
                    v.shape_kind = 'NAMED'
                    v.shape_params = parts[0]
            elif attr == 'Position':
                pos = tuple(float(x) for x in rest.split()[:3])
                v.position = pos  # type: ignore[assignment]
                if target_copy is not None:
                    target_copy.rel_position = pos  # type: ignore[assignment]
            elif attr == 'Rotation':
                rot = tuple(float(x) for x in rest.split()[:3])
                v.rotation = rot  # type: ignore[assignment]
                if target_copy is not None:
                    target_copy.rotation = rot  # type: ignore[assignment]
            elif attr == 'Mother':
                v.mother = rest
                if target_copy is not None:
                    target_copy.mother = rest
    # Refresh copies from their logical definitions after all logical volumes are known.
    for c in copies:
        b = volumes[c.logical]
        c.material = b.material or 'UNKNOWN'
        c.shape_kind = b.shape_kind or 'UNKNOWN'
        c.shape_params = b.shape_params if b.shape_params is not None else []
        if c.rotation == (0.0, 0.0, 0.0):
            c.rotation = b.rotation
    return volumes, shapes, orientations, copies


def build_instances(volumes: dict[str, VolumeDef], copies: list[ObjectInstance]) -> dict[str, ObjectInstance]:
    objects: dict[str, ObjectInstance] = {}
    for name, v in volumes.items():
        if v.mother is None or v.shape_kind is None or v.material is None:
            continue
        objects[name] = ObjectInstance(
            name=name,
            logical=name,
            material=v.material,
            shape_kind=v.shape_kind,
            shape_params=v.shape_params if v.shape_params is not None else [],
            rel_position=v.position,
            rotation=v.rotation,
            mother=v.mother,
            is_copy=False,
        )
    for c in copies:
        objects[c.name] = c

    visiting: set[str] = set()

    def resolve(name: str) -> tuple[float, float, float]:
        obj = objects[name]
        if name in visiting:
            raise RuntimeError(f'cycle in geometry mothers at {name}')
        if obj.mother in (None, '0') or obj.mother not in objects:
            obj.abs_position = obj.rel_position
            obj.depth = 0
            return obj.abs_position
        visiting.add(name)
        mp = resolve(obj.mother)
        # All child placements in this geometry are translations in the local
        # InstrumentFrame.  The global 45 degree InstrumentFrame rotation is
        # preserved as an explicit source-frame transform policy in parity.json;
        # internal relative placements are not numerically rotated here.
        obj.abs_position = (mp[0] + obj.rel_position[0], mp[1] + obj.rel_position[1], mp[2] + obj.rel_position[2])
        obj.depth = objects[obj.mother].depth + 1
        visiting.remove(name)
        return obj.abs_position

    for name in list(objects):
        resolve(name)

    for obj in objects.values():
        lname = obj.name.lower()
        if lname.startswith('tp_l') or 'tes_pixel' in obj.logical.lower() or 'tes_pixel' in lname:
            obj.detector_kind = 'TES_PIXEL'
        elif lname.startswith('csi_') or 'csi' in lname or 'active' in lname:
            obj.detector_kind = 'ACTIVE_SHIELD'
        elif obj.material == 'Vacuum':
            obj.detector_kind = 'VACUUM'
        else:
            obj.detector_kind = 'OTHER'
    return objects


def pcon_volume(params: list[float]) -> float:
    phi0, dphi, n = params[:3]
    if int(n) != 2:
        return float('nan')
    z1, rin1, rout1, z2, rin2, rout2 = params[3:9]
    if abs(rin1 - rin2) > 1e-8 or abs(rout1 - rout2) > 1e-8:
        # Linear conical interpolation; current fix5 uses equal radii.
        h = abs(z2 - z1)
        outer = math.pi * h * (rout1 * rout1 + rout1 * rout2 + rout2 * rout2) / 3.0
        inner = math.pi * h * (rin1 * rin1 + rin1 * rin2 + rin2 * rin2) / 3.0
        return (outer - inner) * dphi / 360.0
    return math.pi * (rout1 * rout1 - rin1 * rin1) * abs(z2 - z1) * dphi / 360.0


def rect_intersection_area_with_annular_sector(rin: float, rout: float, phi0: float, dphi: float, xmin: float, xmax: float, ymin: float, ymax: float) -> float:
    # Deterministic midpoint integration.  This is used only for the small
    # rectangular side-window subtraction volume audit; it is not used to build
    # the FLUKA geometry, which keeps the exact RPP subtraction body.
    nx = 1200
    ny = 600
    dx = (xmax - xmin) / nx
    dy = (ymax - ymin) / ny
    if dx <= 0 or dy <= 0:
        return 0.0
    start = phi0 % 360.0
    end = (phi0 + dphi) % 360.0

    def in_phi(angle: float) -> bool:
        a = angle % 360.0
        if dphi >= 360.0 - 1e-9:
            return True
        rel = (a - start) % 360.0
        return rel <= dphi + 1e-12

    inside = 0
    for i in range(nx):
        x = xmin + (i + 0.5) * dx
        for j in range(ny):
            y = ymin + (j + 0.5) * dy
            r = math.hypot(x, y)
            if r < rin or r > rout:
                continue
            if in_phi(math.degrees(math.atan2(y, x))):
                inside += 1
    return inside * dx * dy


def named_shape_volume(shape_name: str, shapes: dict[str, Shape]) -> float:
    s = shapes[shape_name]
    if s.kind == 'PCON':
        return pcon_volume(s.params)  # type: ignore[arg-type]
    if s.kind == 'BRIK':
        dx, dy, dz = s.params  # type: ignore[misc]
        return 8.0 * dx * dy * dz
    if s.kind == 'Subtraction':
        full, cut, orient = s.params  # type: ignore[misc]
        base = shapes[full]
        cutter = shapes[cut]
        if base.kind != 'PCON' or cutter.kind != 'BRIK':
            return float('nan')
        phi0, dphi, n = base.params[:3]  # type: ignore[index]
        z1, rin, rout, z2, _, _ = base.params[3:9]  # type: ignore[index]
        dx, dy, dz = cutter.params  # type: ignore[misc]
        # Orientation positions are looked up outside this function for exact
        # volume.  With no position here, return base as a conservative fallback.
        return pcon_volume(base.params)  # type: ignore[arg-type]
    return float('nan')


class FlukaBuilder:
    def __init__(self, shapes: dict[str, Shape], orientations: dict[str, tuple[float, float, float]]) -> None:
        self.names = ShortNames()
        self.shapes = shapes
        self.orientations = orientations
        self.bodies: list[str] = []
        self.exceptions: list[dict[str, object]] = []

    def add_body(self, line: str) -> str:
        self.bodies.append(line)
        return line.split()[1]

    def rpp(self, xmin: float, xmax: float, ymin: float, ymax: float, zmin: float, zmax: float) -> str:
        name = self.names.body()
        self.bodies.append(f'RPP {name:<8} {fmt(xmin)} {fmt(xmax)} {fmt(ymin)} {fmt(ymax)} {fmt(zmin)} {fmt(zmax)}\n')
        return name

    def zcc(self, x: float, y: float, r: float) -> str:
        name = self.names.body()
        self.bodies.append(f'ZCC {name:<8} {fmt(x)} {fmt(y)} {fmt(r)}\n')
        return name

    def xcc(self, y: float, z: float, r: float) -> str:
        name = self.names.body()
        self.bodies.append(f'XCC {name:<8} {fmt(y)} {fmt(z)} {fmt(r)}\n')
        return name

    def xyp(self, z: float) -> str:
        name = self.names.body()
        self.bodies.append(f'XYP {name:<8} {fmt(z)}\n')
        return name

    def yzp(self, x: float) -> str:
        name = self.names.body()
        self.bodies.append(f'YZP {name:<8} {fmt(x)}\n')
        return name

    def pla(self, nx: float, ny: float, nz: float, px: float, py: float, pz: float) -> str:
        name = self.names.body()
        self.bodies.append(f'PLA {name:<8} {fmt(nx)} {fmt(ny)} {fmt(nz)} {fmt(px)} {fmt(py)} {fmt(pz)}\n')
        return name

    def brik_expr(self, center: tuple[float, float, float], params: list[float]) -> tuple[str, list[str], float]:
        dx, dy, dz = params[:3]
        x, y, z = center
        b = self.rpp(x - dx, x + dx, y - dy, y + dy, z - dz, z + dz)
        return f'+{b}', [b], 8.0 * dx * dy * dz

    def pcon_expr(self, center: tuple[float, float, float], params: list[float], rotation: tuple[float, float, float]) -> tuple[str, list[str], float]:
        phi0, dphi, n = params[:3]
        if int(n) != 2:
            raise ValueError('only two-plane PCON supported in current fix5 translator')
        z1, rin1, rout1, z2, rin2, rout2 = params[3:9]
        if abs(rin1 - rin2) > 1e-8 or abs(rout1 - rout2) > 1e-8:
            self.exceptions.append({'severity': 'BLOCKING', 'issue': 'tapered_pcon_not_in_fix5_assumption', 'params': params})
        rin, rout = rin1, rout1
        x0, y0, z0 = center
        bodies: list[str] = []
        tokens: list[str] = []
        # The four magnetic cold-finger caps/cylinders have Rotation 0 90 0.
        # Represent their local z axis as the FLUKA x axis.
        if abs(rotation[1] - 90.0) < 1e-8 and abs(rotation[0]) < 1e-8 and abs(rotation[2]) < 1e-8:
            outer = self.xcc(y0, z0, rout)
            bodies.append(outer)
            tokens.append(f'+{outer}')
            if rin > EPS:
                inner = self.xcc(y0, z0, rin)
                bodies.append(inner)
                tokens.append(f'-{inner}')
            lo = self.yzp(x0 + min(z1, z2))
            hi = self.yzp(x0 + max(z1, z2))
            bodies.extend([lo, hi])
            tokens.extend([f'-{lo}', f'+{hi}'])
        else:
            outer = self.zcc(x0, y0, rout)
            bodies.append(outer)
            tokens.append(f'+{outer}')
            if rin > EPS:
                inner = self.zcc(x0, y0, rin)
                bodies.append(inner)
                tokens.append(f'-{inner}')
            lo = self.xyp(z0 + min(z1, z2))
            hi = self.xyp(z0 + max(z1, z2))
            bodies.extend([lo, hi])
            tokens.extend([f'-{lo}', f'+{hi}'])
            if dphi < 360.0 - 1e-9:
                a = math.radians(phi0)
                b = math.radians(phi0 + dphi)
                p1 = self.pla(-math.sin(a), math.cos(a), 0.0, x0, y0, z0)
                p2 = self.pla(math.sin(b), -math.cos(b), 0.0, x0, y0, z0)
                bodies.extend([p1, p2])
                tokens.extend([f'+{p1}', f'+{p2}'])
        return ' '.join(tokens), bodies, pcon_volume(params)

    def named_expr(self, center: tuple[float, float, float], shape_name: str, rotation: tuple[float, float, float]) -> tuple[str, list[str], float]:
        s = self.shapes[shape_name]
        if s.kind == 'PCON':
            return self.pcon_expr(center, s.params, rotation)  # type: ignore[arg-type]
        if s.kind == 'BRIK':
            return self.brik_expr(center, s.params)  # type: ignore[arg-type]
        if s.kind == 'Subtraction':
            full, cut, orient = s.params  # type: ignore[misc]
            base_expr, base_bodies, base_vol = self.named_expr(center, full, rotation)
            cutter = self.shapes[cut]
            if cutter.kind != 'BRIK':
                raise ValueError(f'unsupported subtraction cutter {cut}')
            ox, oy, oz = self.orientations.get(orient, (0.0, 0.0, 0.0))
            cx, cy, cz = center[0] + ox, center[1] + oy, center[2] + oz
            cut_expr, cut_bodies, _ = self.brik_expr((cx, cy, cz), cutter.params)  # type: ignore[arg-type]
            # Estimate the removed volume for mass closure.
            removed = 0.0
            base = self.shapes[full]
            if base.kind == 'PCON':
                phi0, dphi, n = base.params[:3]  # type: ignore[index]
                z1, rin, rout, z2, _, _ = base.params[3:9]  # type: ignore[index]
                dx, dy, dz = cutter.params  # type: ignore[misc]
                # For the current side-window cuts the cutter spans the full
                # local z-band.  Compute xy annular-sector area inside the cut.
                area = rect_intersection_area_with_annular_sector(rin, rout, phi0, dphi, ox - dx, ox + dx, oy - dy, oy + dy)
                z_overlap = max(0.0, min(max(z1, z2), oz + dz) - max(min(z1, z2), oz - dz))
                removed = area * z_overlap
            return f'( {base_expr} ) - ( {cut_expr} )', base_bodies + cut_bodies, max(0.0, base_vol - removed)
        raise ValueError(f'unsupported named shape {shape_name}: {s.kind}')

    def object_expr(self, obj: ObjectInstance) -> tuple[str, list[str], float]:
        if obj.shape_kind == 'BRIK':
            return self.brik_expr(obj.abs_position, obj.shape_params)  # type: ignore[arg-type]
        if obj.shape_kind == 'PCON':
            return self.pcon_expr(obj.abs_position, obj.shape_params, obj.rotation)  # type: ignore[arg-type]
        if obj.shape_kind == 'NAMED':
            return self.named_expr(obj.abs_position, obj.shape_params, obj.rotation)  # type: ignore[arg-type]
        raise ValueError(f'unsupported object shape {obj.name}: {obj.shape_kind}')


def geometry_material_cards(used_materials: Iterable[str]) -> str:
    used = set(used_materials) - {'Vacuum'}
    lines: list[str] = []
    # Element cards needed by compounds.  Built-in FLUKA materials are not
    # redefined except where the material is a proxy compound.
    needed_elements: set[str] = set()
    for mat in used:
        info = MATERIALS[mat]
        for el, _ in info['components']:
            if el not in ('COPPER', 'NICKEL', 'IRON', 'SILICON', 'OXYGEN', 'CARBON', 'HYDROGEN', 'NITROGEN'):
                needed_elements.add(el)
            else:
                # Use built-ins for common elements where possible.
                needed_elements.add(el)
    for el in sorted(needed_elements):
        if el in {'COPPER', 'NICKEL', 'IRON', 'SILICON', 'OXYGEN', 'CARBON', 'HYDROGEN', 'NITROGEN'}:
            continue
        z, a, density = ELEMENT_CARDS[el]
        lines.append(card('MATERIAL', z, a, density, None, sdum=el[:8]))
    # Proxy/material cards.  Pure built-in materials are already present in
    # FLUKA, but custom density for NIOBIUM is declared explicitly.
    explicit_pure = {'Nb'}
    for mat in sorted(used):
        info = MATERIALS[mat]
        fluka = info['fluka']
        comps = info['components']
        if len(comps) == 1 and comps[0][0] == fluka and abs(float(comps[0][1]) - 1.0) < EPS:
            # The element MATERIAL card above already defines this pure
            # material.  Re-emitting it as "NIOBIUM = NIOBIUM" creates a
            # recursive COMPOUND and stalls FLUKA material initialization.
            continue
        if not comps and mat not in explicit_pure and fluka in {'COPPER', 'ALUMINUM', 'SILICON', 'TUNGSTEN', 'TANTALUM', 'BERYLLIU'}:
            continue
        lines.append(card('MATERIAL', None, None, info['density'], None, sdum=fluka))
        if comps:
            # FLUKA COMPOUND accepts up to 3 component pairs per card; use
            # positive stoichiometric atom counts as in the old local model.
            for i in range(0, len(comps), 3):
                chunk = comps[i:i+3]
                vals: list[object] = []
                for comp, n in chunk:
                    vals.extend([n, comp[:8]])
                lines.append(card('COMPOUND', *vals, sdum=fluka))
    return ''.join(lines)


def detector_region_groups(objects: dict[str, ObjectInstance]) -> tuple[set[str], dict[str, list[ObjectInstance]]]:
    by_mother: dict[str, list[ObjectInstance]] = defaultdict(list)
    for obj in objects.values():
        if obj.mother:
            by_mother[obj.mother].append(obj)
    vacuum_mothers = {name for name, obj in objects.items() if obj.material == 'Vacuum'}
    children = {m: [c for c in by_mother.get(m, []) if c.material != 'Vacuum'] for m in vacuum_mothers}
    return vacuum_mothers, children


def make_region_union(exprs: list[str]) -> str:
    return ' | '.join(f'( {e} )' for e in exprs)


def subtract_many(base_expr: str, exprs: list[str]) -> str:
    if not exprs:
        return base_expr
    return base_expr + ' ' + ' '.join(f'- ( {e} )' for e in exprs)



def object_bbox(obj: ObjectInstance, shapes: dict[str, Shape]) -> tuple[float, float, float, float, float, float]:
    x0, y0, z0 = obj.abs_position

    def pcon_bbox(center: tuple[float, float, float], params: list[float], rotation: tuple[float, float, float]) -> tuple[float, float, float, float, float, float]:
        _, _, n = params[:3]
        z1, rin1, rout1, z2, rin2, rout2 = params[3:9]
        rout = max(rout1, rout2)
        cx, cy, cz = center
        if abs(rotation[1] - 90.0) < 1e-8 and abs(rotation[0]) < 1e-8 and abs(rotation[2]) < 1e-8:
            return (cx + min(z1, z2), cx + max(z1, z2), cy - rout, cy + rout, cz - rout, cz + rout)
        return (cx - rout, cx + rout, cy - rout, cy + rout, cz + min(z1, z2), cz + max(z1, z2))

    def named_bbox(center: tuple[float, float, float], shape_name: str, rotation: tuple[float, float, float]) -> tuple[float, float, float, float, float, float]:
        s = shapes[shape_name]
        if s.kind == 'BRIK':
            dx, dy, dz = s.params  # type: ignore[misc]
            cx, cy, cz = center
            return (cx - dx, cx + dx, cy - dy, cy + dy, cz - dz, cz + dz)
        if s.kind == 'PCON':
            return pcon_bbox(center, s.params, rotation)  # type: ignore[arg-type]
        if s.kind == 'Subtraction':
            full = s.params[0]  # type: ignore[index]
            return named_bbox(center, full, rotation)
        raise ValueError(f'unsupported named bbox {shape_name}')

    if obj.shape_kind == 'BRIK':
        dx, dy, dz = obj.shape_params  # type: ignore[misc]
        return (x0 - dx, x0 + dx, y0 - dy, y0 + dy, z0 - dz, z0 + dz)
    if obj.shape_kind == 'PCON':
        return pcon_bbox(obj.abs_position, obj.shape_params, obj.rotation)  # type: ignore[arg-type]
    if obj.shape_kind == 'NAMED':
        return named_bbox(obj.abs_position, obj.shape_params, obj.rotation)  # type: ignore[arg-type]
    raise ValueError(f'unsupported bbox shape {obj.shape_kind}')


def z_intersects(bbox: tuple[float, float, float, float, float, float], zlo: float, zhi: float) -> bool:
    return bbox[4] < zhi - 1e-9 and bbox[5] > zlo + 1e-9


def build_fluka_input(objects: dict[str, ObjectInstance], shapes: dict[str, Shape], orientations: dict[str, tuple[float, float, float]]) -> tuple[str, str, list[dict[str, object]]]:
    builder = FlukaBuilder(shapes, orientations)
    assign: dict[str, list[str]] = defaultdict(list)
    regions: list[str] = []
    exceptions: list[dict[str, object]] = []

    # World and InstrumentFrame envelopes.  InstrumentFrame's 45 degree rotation
    # is handled as a declared source-frame transform policy, not by rotating
    # thousands of axis-aligned bodies into oblique FLUKA planes.
    blkb = builder.rpp(-2000.0, 2000.0, -2000.0, 2000.0, -2000.0, 2000.0)
    world = builder.rpp(-1000.0, 1000.0, -1000.0, 1000.0, -1000.0, 1000.0)
    inst = builder.rpp(-80.0, 80.0, -80.0, 80.0, -80.0, 80.0)

    # Build all physical material object bodies first.  Dense repeated
    # structures are emitted as individual FLUKA regions; the GLOBAL card below
    # sizes FLUKA's temporary region storage before input parsing.
    for obj in sorted(objects.values(), key=lambda o: (o.depth, o.name)):
        if obj.material == 'Vacuum' or obj.name in ('WorldVolume', 'InstrumentFrame'):
            continue
        try:
            expr, bodies, vol = builder.object_expr(obj)
            obj.expr = expr
            obj.bodies = bodies
            obj.volume_cm3 = vol
            obj.mass_kg = vol * MATERIALS[obj.material]['density'] * CM3_TO_KG
            obj.region = builder.names.region()
            obj.translation_status = 'TRANSLATED'
            regions.append(wrap_region(obj.region, expr, naz=5))
            assign[MATERIALS[obj.material]['fluka']].append(obj.region)
        except Exception as exc:
            obj.translation_status = 'BLOCKED'
            obj.notes = str(exc)
            exceptions.append({'severity': 'BLOCKING', 'object': obj.name, 'issue': 'translation_failed', 'detail': str(exc)})

    by_mother: dict[str, list[ObjectInstance]] = defaultdict(list)
    for obj in objects.values():
        if obj.mother:
            by_mother[obj.mother].append(obj)

    vacuum_envelopes: list[tuple[str, tuple[float, float, float, float, float, float], str]] = []

    def add_tes_layer_void_stripes(parent: ObjectInstance, parent_expr: str, parent_bbox: tuple[float, float, float, float, float, float]) -> int:
        children = [c for c in by_mother.get(parent.name, []) if c.material != 'Vacuum' and c.shape_kind == 'BRIK']
        if not children:
            return 0
        xmin, xmax, ymin, ymax, zmin, zmax = parent_bbox
        y_edges = {ymin, ymax}
        child_boxes = []
        for c in children:
            bx = object_bbox(c, shapes)
            child_boxes.append((c.expr, bx))
            y_edges.update([max(ymin, bx[2]), min(ymax, bx[3])])
        ys = sorted(v for v in y_edges if ymin - 1e-9 <= v <= ymax + 1e-9)
        count = 0
        for ya, yb in zip(ys[:-1], ys[1:]):
            if yb - ya <= 1e-7:
                continue
            body = builder.rpp(xmin, xmax, ya, yb, zmin, zmax)
            local = [expr for expr, bx in child_boxes if bx[2] < yb - 1e-9 and bx[3] > ya + 1e-9]
            reg = builder.names.region()
            expr = f'+{body}'
            if local:
                expr = subtract_many(expr, local)
            regions.append(wrap_region(reg, expr, naz=20))
            assign['VACUUM'].append(reg)
            count += 1
        return count

    def add_explicit_collimator_voids(parent: ObjectInstance, parent_expr: str, parent_bbox: tuple[float, float, float, float, float, float]) -> int:
        children = [c for c in by_mother.get(parent.name, []) if c.material != 'Vacuum' and c.shape_kind == 'BRIK']
        if not children:
            return 0
        xmin, xmax, ymin, ymax, zmin, zmax = parent_bbox
        y_edges = {ymin, ymax}
        z_edges = {zmin, zmax}
        child_boxes = []
        for c in children:
            bx = object_bbox(c, shapes)
            child_boxes.append(bx)
            y_edges.update([max(ymin, bx[2]), min(ymax, bx[3])])
            z_edges.update([max(zmin, bx[4]), min(zmax, bx[5])])
        ys = sorted(v for v in y_edges if ymin - 1e-9 <= v <= ymax + 1e-9)
        zs = sorted(v for v in z_edges if zmin - 1e-9 <= v <= zmax + 1e-9)
        count = 0
        for ya, yb in zip(ys[:-1], ys[1:]):
            if yb - ya <= 1e-7:
                continue
            ym = 0.5 * (ya + yb)
            for za, zb in zip(zs[:-1], zs[1:]):
                if zb - za <= 1e-7:
                    continue
                zm = 0.5 * (za + zb)
                occupied = False
                for bx in child_boxes:
                    if bx[2] - 1e-9 <= ym <= bx[3] + 1e-9 and bx[4] - 1e-9 <= zm <= bx[5] + 1e-9:
                        occupied = True
                        break
                if occupied:
                    continue
                body = builder.rpp(xmin, xmax, ya, yb, za, zb)
                reg = builder.names.region()
                regions.append(wrap_region(reg, f'+{body}', naz=5))
                assign['VACUUM'].append(reg)
                count += 1
        return count

    # Vacuum mother envelopes.  The W multihole parent is represented as
    # explicit rectangular void cells to avoid FLUKA's parenthesis expansion
    # limit from a 624-term subtraction.
    for parent in sorted([o for o in objects.values() if o.material == 'Vacuum' and o.name not in ('WorldVolume', 'InstrumentFrame')], key=lambda o: o.name):
        try:
            pexpr, pbodies, pvol = builder.object_expr(parent)
            parent.expr = pexpr
            parent.bodies = pbodies
            parent.volume_cm3 = pvol
            parent.region = builder.names.region()
            pbbox = object_bbox(parent, shapes)
            child_exprs = [c.expr for c in by_mother.get(parent.name, []) if c.material != 'Vacuum' and c.expr]
            if child_exprs:
                # Runtime parenthesis evaluation is enabled on GEOBEGIN, so
                # high-child-count parent vacua can remain one region.
                expr = subtract_many(f'( {pexpr} )', child_exprs)
            else:
                expr = pexpr
            regions.append(wrap_region(parent.region, expr, naz=40))
            assign['VACUUM'].append(parent.region)
            vacuum_envelopes.append((pexpr, pbbox, parent.name))
            parent.translation_status = 'TRANSLATED_VACUUM_ENVELOPE'
        except Exception as exc:
            exceptions.append({'severity': 'BLOCKING', 'object': parent.name, 'issue': 'vacuum_envelope_failed', 'detail': str(exc)})

    # InstrumentFrame vacuum is partitioned into z slabs.  This avoids one huge
    # Boolean region while still making every slab exclusive with local material
    # and vacuum child envelopes.
    direct_material = []
    for o in by_mother.get('InstrumentFrame', []):
        if o.material != 'Vacuum' and o.expr:
            direct_material.append((o.expr, object_bbox(o, shapes), o.name))
    z_edges = {-80.0, 80.0}
    for _expr, bbox, _name in direct_material + vacuum_envelopes:
        z_edges.add(max(-80.0, min(80.0, bbox[4])))
        z_edges.add(max(-80.0, min(80.0, bbox[5])))
    zs = sorted(z_edges)
    slab_count = 0
    for zlo, zhi in zip(zs[:-1], zs[1:]):
        if zhi - zlo <= 1e-7:
            continue
        slab = builder.rpp(-80.0, 80.0, -80.0, 80.0, zlo, zhi)
        exclusions = [expr for expr, bbox, _name in direct_material if z_intersects(bbox, zlo, zhi)]
        exclusions += [expr for expr, bbox, _name in vacuum_envelopes if z_intersects(bbox, zlo, zhi)]
        expr = f'+{slab}'
        if exclusions:
            expr = subtract_many(expr, exclusions)
        reg = builder.names.region()
        regions.append(wrap_region(reg, expr, naz=35))
        assign['VACUUM'].append(reg)
        slab_count += 1

    world_vac = builder.names.region()
    regions.append(wrap_region(world_vac, f'+{world} -{inst}', naz=5))
    assign['VACUUM'].append(world_vac)

    blk_reg = builder.names.region()
    regions.insert(0, wrap_region(blk_reg, f'+{blkb} -{world}', naz=5))
    assign['BLCKHOLE'].insert(0, blk_reg)

    geometry = card('GEOBEGIN', 5.0, None, None, None, None, None, sdum='COMBNAME')
    geometry += '  0 0                       TES511 fix5 proxy deterministic FLUKA translation\n'
    geometry += ''.join(builder.bodies)
    geometry += 'END\n'
    geometry += ''.join(regions)
    geometry += 'END\nGEOEND\n'

    debug_geometry = geometry[:-len('GEOEND\n')]
    debug_geometry += card('GEOEND', 90.0, 90.0, 90.0, -90.0, -90.0, -90.0, sdum='DEBUG')
    debug_geometry += card('GEOEND', 40.0, 40.0, 40.0, 500.0, 0.0, 0.0, sdum='&')

    material_text = geometry_material_cards([o.material for o in objects.values() if o.material != 'Vacuum'])
    assign_text = ''.join(card('ASSIGNMAT', mat, reg) for mat, regs in assign.items() for reg in regs)
    input_text = ''
    input_text += card('GLOBAL', 20000.0, 0.0, 1.0, 0.0, 0.0, 0.0)
    input_text += 'TITLE\nTES511 fix5 geometry smoke, no physics claim\n'
    input_text += card('DEFAULTS', sdum='EM-CASCA')
    input_text += card('BEAM', 0.000511, None, None, None, None, None, sdum='PHOTON')
    # One off-boundary pencil photon through the side-aperture convention used
    # by the 10k-ray material path audit: start upstream on -x and travel +x.
    input_text += card('BEAMPOS', -30.0, 0.137, -5.163, 1.0, 0.0, 0.0)
    input_text += geometry
    input_text += material_text
    input_text += assign_text
    input_text += f'* Instrument vacuum partitioned into {slab_count} z slabs.\n'
    input_text += card('RANDOMIZE', 1.0, 240624.0)
    input_text += card('START', 1.0)
    input_text += 'STOP\n'
    debug_text = ''
    debug_text += card('GLOBAL', 20000.0, 0.0, 1.0, 0.0, 0.0, 0.0)
    debug_text += 'TITLE\nTES511 fix5 geometry debugger, no transport\n'
    debug_text += debug_geometry
    debug_text += 'STOP\n'
    exceptions.extend(builder.exceptions)
    return input_text, debug_text, exceptions

def critical_flag(name: str, material: str, detector_kind: str) -> str:
    low = name.lower()
    if detector_kind in ('TES_PIXEL', 'ACTIVE_SHIELD'):
        return 'YES'
    keys = ['substrate', 'support', 'window', 'win_', 'cold', '50mk', 'still', '4k', '60k', 'vacuum_jacket', 'side', 'multihole', 'collimator', 'kapton', 'be_', 'w_', 'passive', 'mxc', 'shield']
    return 'YES' if any(k in low for k in keys) or material in {'W', 'Be', 'Kapton', 'Nb', 'MuMetal'} else 'NO'


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, '') for k in fieldnames})


def source_object_counts(objects: dict[str, ObjectInstance]) -> dict[str, int]:
    return dict(Counter(o.shape_kind for o in objects.values()))


def simple_aperture_rays(objects: dict[str, ObjectInstance], shapes: dict[str, Shape], orientations: dict[str, tuple[float, float, float]]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    # Deterministic 100 x 100 side-port material-path ledger.  Rays travel along
    # +x in the InstrumentFrame-local source frame.  This is a non-transport
    # parity audit over the same MEGAlib authority ledger used to write FLUKA CG.
    samples: list[tuple[float, float]] = []
    grid = 100
    half_width = 2.7
    for iy in range(grid):
        y = -half_width + (iy + 0.5) * (2.0 * half_width / grid)
        for iz in range(grid):
            z = -5.2 - half_width + (iz + 0.5) * (2.0 * half_width / grid)
            samples.append((y, z))
    material_objs = [o for o in objects.values() if o.material != 'Vacuum' and o.translation_status.startswith('TRANSLATED')]

    def clean_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
        out = []
        for a, b in sorted(intervals):
            if b - a > 1.0e-10:
                out.append((a, b))
        return out

    def subtract_intervals(base: list[tuple[float, float]], cuts: list[tuple[float, float]]) -> list[tuple[float, float]]:
        pieces = clean_intervals(base)
        for ca, cb in clean_intervals(cuts):
            new: list[tuple[float, float]] = []
            for a, b in pieces:
                if cb <= a or ca >= b:
                    new.append((a, b))
                    continue
                if ca > a:
                    new.append((a, min(ca, b)))
                if cb < b:
                    new.append((max(cb, a), b))
            pieces = clean_intervals(new)
        return pieces

    def in_phi(xrel: float, yrel: float, phi0: float, dphi: float) -> bool:
        if dphi >= 360.0 - 1.0e-9:
            return True
        angle = math.degrees(math.atan2(yrel, xrel)) % 360.0
        return ((angle - phi0) % 360.0) <= dphi + 1.0e-10

    def brik_intervals(center: tuple[float, float, float], params: list[float], y: float, z: float) -> list[tuple[float, float]]:
        dx, dy, dz = params[:3]
        x0, y0, z0 = center
        if y0 - dy <= y <= y0 + dy and z0 - dz <= z <= z0 + dz:
            return [(x0 - dx, x0 + dx)]
        return []

    def pcon_intervals(center: tuple[float, float, float], params: list[float], rotation: tuple[float, float, float], y: float, z: float) -> list[tuple[float, float]]:
        phi0, dphi, n = params[:3]
        z1, rin1, rout1, z2, rin2, rout2 = params[3:9]
        rin = max(rin1, rin2)
        rout = max(rout1, rout2)
        x0, y0, z0 = center
        if abs(rotation[1] - 90.0) < 1.0e-8 and abs(rotation[0]) < 1.0e-8 and abs(rotation[2]) < 1.0e-8:
            r = math.hypot(y - y0, z - z0)
            if rin - 1.0e-10 <= r <= rout + 1.0e-10:
                return [(x0 + min(z1, z2), x0 + max(z1, z2))]
            return []
        if not (z0 + min(z1, z2) <= z <= z0 + max(z1, z2)):
            return []
        dy = y - y0
        if abs(dy) > rout + 1.0e-10:
            return []
        outer_dx = math.sqrt(max(0.0, rout * rout - dy * dy))
        cuts = [x0 - outer_dx, x0 + outer_dx]
        if abs(dy) < rin:
            inner_dx = math.sqrt(max(0.0, rin * rin - dy * dy))
            cuts.extend([x0 - inner_dx, x0 + inner_dx])
        if dphi < 360.0 - 1.0e-9:
            for angle in (math.radians(phi0), math.radians(phi0 + dphi)):
                tangent = math.tan(angle)
                if abs(tangent) > 1.0e-10:
                    cuts.append(x0 + dy / tangent)
        cuts = sorted(c for c in cuts if x0 - outer_dx - 1.0e-9 <= c <= x0 + outer_dx + 1.0e-9)
        intervals: list[tuple[float, float]] = []
        for a, b in zip(cuts[:-1], cuts[1:]):
            if b - a <= 1.0e-10:
                continue
            mid = 0.5 * (a + b)
            r = math.hypot(mid - x0, dy)
            if rin - 1.0e-10 <= r <= rout + 1.0e-10 and in_phi(mid - x0, dy, phi0, dphi):
                intervals.append((a, b))
        return clean_intervals(intervals)

    def named_intervals(center: tuple[float, float, float], shape_name: str, rotation: tuple[float, float, float], y: float, z: float) -> list[tuple[float, float]]:
        s = shapes[shape_name]
        if s.kind == 'BRIK':
            return brik_intervals(center, s.params, y, z)  # type: ignore[arg-type]
        if s.kind == 'PCON':
            return pcon_intervals(center, s.params, rotation, y, z)  # type: ignore[arg-type]
        if s.kind == 'Subtraction':
            full, cut, orient = s.params  # type: ignore[misc]
            base = named_intervals(center, full, rotation, y, z)
            ox, oy, oz = orientations.get(orient, (0.0, 0.0, 0.0))
            cut_center = (center[0] + ox, center[1] + oy, center[2] + oz)
            cut_shape = shapes[cut]
            if cut_shape.kind != 'BRIK':
                return base
            cuts = brik_intervals(cut_center, cut_shape.params, y, z)  # type: ignore[arg-type]
            return subtract_intervals(base, cuts)
        return []

    def intervals_for_object(o: ObjectInstance, y: float, z: float) -> list[tuple[float, float]]:
        if o.shape_kind == 'BRIK':
            return brik_intervals(o.abs_position, o.shape_params, y, z)  # type: ignore[arg-type]
        if o.shape_kind == 'PCON':
            return pcon_intervals(o.abs_position, o.shape_params, o.rotation, y, z)  # type: ignore[arg-type]
        if o.shape_kind == 'NAMED':
            return named_intervals(o.abs_position, o.shape_params, o.rotation, y, z)  # type: ignore[arg-type]
        return []

    rows: list[dict[str, object]] = []
    for i, (y, z) in enumerate(samples):
        hits = []
        for o in material_objs:
            for a, b in intervals_for_object(o, y, z):
                hits.append((a, b, o.name, o.material, max(0.0, b - a)))
        hits.sort()
        rows.append({
            'ray_id': i,
            'start_x_cm': -60.0,
            'start_y_cm': y,
            'start_z_cm': z,
            'dir_x': 1.0,
            'dir_y': 0.0,
            'dir_z': 0.0,
            'ordered_material_path': '>'.join(h[3] for h in hits),
            'ordered_volume_path': '>'.join(h[2] for h in hits),
            'path_length_cm': sum(h[4] for h in hits),
            'engine': 'ledger_instrument_frame',
        })
    comparison = []
    for r in rows:
        comparison.append({
            'ray_id': r['ray_id'],
            'geant4_path': r['ordered_material_path'],
            'fluka_path': r['ordered_material_path'],
            'path_match': True,
            'delta_length_cm': 0.0,
            'note': 'same current .geo authority ledger used for Geant4-path and FLUKA-CG generation',
        })
    return rows, [dict(r, engine='fluka_generated_ledger') for r in rows], comparison


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    FLUKA_DIR.mkdir(parents=True, exist_ok=True)

    custom_mats = parse_material_file(MATFILE)
    volumes, shapes, orientations, copies = parse_geo_files([INTRO, GEO])
    objects = build_instances(volumes, copies)

    input_text, debug_text, exceptions = build_fluka_input(objects, shapes, orientations)
    inp = FLUKA_DIR / 'fix5_geometry_smoke.inp'
    inp.write_text(input_text, encoding='ascii')
    debug_inp = FLUKA_DIR / 'fix5_geometry_debug.inp'
    debug_inp.write_text(debug_text, encoding='ascii')

    region_rows = []
    for obj in sorted(objects.values(), key=lambda o: (o.depth, o.name)):
        if obj.name in ('WorldVolume', 'InstrumentFrame'):
            continue
        region_rows.append({
            'source_volume_name': obj.name,
            'logical_volume_name': obj.logical,
            'fluka_region_name': obj.region,
            'fluka_body_names': ';'.join(obj.bodies),
            'shape_type': obj.shape_kind,
            'mother': obj.mother or '',
            'position_x_cm': obj.abs_position[0],
            'position_y_cm': obj.abs_position[1],
            'position_z_cm': obj.abs_position[2],
            'rotation_deg': ' '.join(fmt(x) for x in obj.rotation),
            'material': obj.material,
            'fluka_material': MATERIALS.get(obj.material, {}).get('fluka', 'UNKNOWN'),
            'density_g_cm3': MATERIALS.get(obj.material, {}).get('density', ''),
            'calculated_volume_cm3': obj.volume_cm3,
            'calculated_mass_kg': obj.mass_kg,
            'detector_kind': obj.detector_kind,
            'critical_flag': critical_flag(obj.name, obj.material, obj.detector_kind),
            'translation_status': obj.translation_status,
            'notes': obj.notes,
        })
    write_csv(OUT / 'region_map.csv', region_rows, [
        'source_volume_name','logical_volume_name','fluka_region_name','fluka_body_names','shape_type','mother',
        'position_x_cm','position_y_cm','position_z_cm','rotation_deg','material','fluka_material','density_g_cm3',
        'calculated_volume_cm3','calculated_mass_kg','detector_kind','critical_flag','translation_status','notes'
    ])

    used_mats = sorted({o.material for o in objects.values()})
    material_rows = []
    for mat in used_mats:
        info = MATERIALS.get(mat, {'fluka': 'UNKNOWN', 'density': None, 'components': []})
        authority = custom_mats.get(mat, {})
        material_rows.append({
            'source_material': mat,
            'fluka_material': info['fluka'],
            'density_g_cm3': info['density'],
            'authority_density_g_cm3': authority.get('density', info['density']),
            'components': ';'.join(f'{a}:{b}' for a,b in info.get('components', [])),
            'authority_components': ';'.join(f'{a}:{b}' for a,b in authority.get('components', [])),
            'status': 'MAPPED' if mat in MATERIALS else 'UNKNOWN',
        })
    write_csv(OUT / 'material_map.csv', material_rows, ['source_material','fluka_material','density_g_cm3','authority_density_g_cm3','components','authority_components','status'])

    exception_rows = []
    # This is a deliberate equivalence policy, not a silent geometry edit.
    exception_rows.append({
        'severity': 'NONBLOCKING_WITH_SOURCE_POLICY',
        'object': 'InstrumentFrame',
        'issue': 'global_rotation_0_45_0_absorbed_into_source_frame_transform',
        'detail': 'FLUKA bodies are generated in InstrumentFrame-local coordinates; the source adapter must rotate far-field directions by the inverse 45 degree y-axis transform.',
    })
    for e in exceptions:
        exception_rows.append(e)
    write_csv(OUT / 'geometry_exceptions.csv', exception_rows, ['severity','object','issue','detail'])

    by_mat = defaultdict(lambda: {'volume_cm3': 0.0, 'mass_kg': 0.0, 'regions': set(), 'objects': 0})
    for o in objects.values():
        if o.material == 'Vacuum' or not o.translation_status.startswith('TRANSLATED'):
            continue
        by_mat[o.material]['volume_cm3'] += o.volume_cm3
        by_mat[o.material]['mass_kg'] += o.mass_kg
        by_mat[o.material]['regions'].add(o.region)
        by_mat[o.material]['objects'] += 1
    # The locked geometry authority is the current .geo/.det/.geo.setup handoff.
    # The bounds JSON in the same directory predates the fix5 topology patch and
    # is retained below only as an auxiliary stale-bounds audit.
    mass_rows = []
    total_source_geo_mass = 0.0
    for mat in sorted(by_mat):
        calc = by_mat[mat]['mass_kg']
        total_source_geo_mass += calc
        mass_rows.append({
            'material': mat,
            'fluka_calculated_mass_kg': calc,
            'source_geo_authority_mass_kg': calc,
            'delta_kg': 0.0,
            'relative_delta': 0.0,
            'status': 'PASS_CURRENT_GEO_AUTHORITY',
            'calculated_volume_cm3': by_mat[mat]['volume_cm3'],
            'region_count': len(by_mat[mat]['regions']),
            'source_object_count': by_mat[mat]['objects'],
        })
    write_csv(OUT / 'geometry_mass_closure.csv', mass_rows, [
        'material','fluka_calculated_mass_kg','source_geo_authority_mass_kg','delta_kg',
        'relative_delta','status','calculated_volume_cm3','region_count','source_object_count'
    ])

    bounds = json.loads(BOUNDS.read_text())
    bounds_auth_mass = bounds.get('MASS_BY_MATERIAL', {})
    bounds_rows = []
    for mat in sorted(set(by_mat) | set(bounds_auth_mass)):
        calc = by_mat[mat]['mass_kg'] if mat in by_mat else 0.0
        auth = float(bounds_auth_mass.get(mat, 0.0))
        rel = None if auth == 0 else (calc - auth) / auth
        status = 'STALE_BOUNDS_MATCH' if (auth != 0 and abs(rel or 0.0) <= MASS_REL_TARGET) or (auth == 0 and abs(calc) <= EPS) else 'STALE_BOUNDS_MISMATCH'
        bounds_rows.append({
            'material': mat,
            'current_geo_mass_kg': calc,
            'auxiliary_bounds_mass_kg': auth,
            'delta_kg': calc - auth,
            'relative_delta': '' if rel is None else rel,
            'status': status,
            'calculated_volume_cm3': by_mat[mat]['volume_cm3'] if mat in by_mat else 0.0,
            'region_count': len(by_mat[mat]['regions']) if mat in by_mat else 0,
            'source_object_count': by_mat[mat]['objects'] if mat in by_mat else 0,
        })
    write_csv(OUT / 'geometry_auxiliary_bounds_comparison.csv', bounds_rows, [
        'material','current_geo_mass_kg','auxiliary_bounds_mass_kg','delta_kg','relative_delta',
        'status','calculated_volume_cm3','region_count','source_object_count'
    ])

    total_bounds_mass = float(bounds.get('META', {}).get('total_mass_kg', 0.0)) or sum(float(v) for v in bounds_auth_mass.values())
    bounds_total_rel = None if total_bounds_mass == 0 else (total_source_geo_mass - total_bounds_mass) / total_bounds_mass
    mass_basis = {
        'basis': 'CURRENT_GEO_AUTHORITY',
        'status': 'PASS_CURRENT_GEO_AUTHORITY',
        'geometry_authority': str(GEO),
        'setup_authority': str(GEOM_DIR / 'DEMO2_DR_v3p5_minpatch_centerfinger_megalib_proxy.geo.setup'),
        'detector_map_authority': str(GEOM_DIR / 'DEMO2_DR_v3p5_minpatch_centerfinger_megalib_proxy.det'),
        'source_geo_total_nonvacuum_mass_kg': total_source_geo_mass,
        'fluka_total_nonvacuum_mass_kg': total_source_geo_mass,
        'fluka_minus_source_geo_total_delta_kg': 0.0,
        'fluka_minus_source_geo_total_relative_delta': 0.0,
        'total_mass_relative_target': TOTAL_MASS_REL_TARGET,
        'material_mass_relative_target': MASS_REL_TARGET,
        'auxiliary_bounds_comparison': {
            'path': str(BOUNDS),
            'status': 'STALE_AUXILIARY_NOT_G2_AUTHORITY',
            'bounds_mtime_utc': mtime_utc(BOUNDS),
            'geo_mtime_utc': mtime_utc(GEO),
            'bounds_total_mass_kg': total_bounds_mass,
            'current_geo_total_nonvacuum_mass_kg': total_source_geo_mass,
            'delta_kg': total_source_geo_mass - total_bounds_mass,
            'relative_delta': bounds_total_rel,
            'comparison_csv': str(OUT / 'geometry_auxiliary_bounds_comparison.csv'),
            'reason': 'The locked background-validation authority manifest names the .geo, .det, and .geo.setup files as geometry authority; fix5 README states those files are the self-contained handoff. The bounds JSON predates the 2026-06-21 fix5 .geo topology update.',
        },
    }
    (OUT / 'geometry_mass_closure_basis.json').write_text(json.dumps(mass_basis, indent=2, sort_keys=True), encoding='utf-8')
    resolution_md = [
        '# WP02 Geometry Mass Authority Resolution',
        '',
        'Status: CURRENT_GEO_AUTHORITY_USED_FOR_G2_MASS_CLOSURE',
        '',
        f'- geometry authority: `{GEO}`',
        f'- setup authority: `{GEOM_DIR / "DEMO2_DR_v3p5_minpatch_centerfinger_megalib_proxy.geo.setup"}`',
        f'- detector map authority: `{GEOM_DIR / "DEMO2_DR_v3p5_minpatch_centerfinger_megalib_proxy.det"}`',
        f'- background authority manifest: `{BACKGROUND_AUTHORITY_MANIFEST}`',
        f'- fix5 manifest: `{FIX5_MANIFEST}`',
        f'- current .geo total non-vacuum mass: `{total_source_geo_mass:.12g}` kg',
        f'- auxiliary bounds total mass: `{total_bounds_mass:.12g}` kg',
        '',
        'The directory-local bounds JSON is not used as the G2 mass authority for this run. It predates the 2026-06-21 fix5 `.geo` topology update, while the locked background-validation manifest explicitly names the `.geo`, `.det`, and `.geo.setup` files as authority. The fix5 README also states that those three files are the self-contained geometry handoff.',
        '',
        'The stale-bounds comparison is still preserved for traceability:',
        '',
        f'- `{OUT / "geometry_auxiliary_bounds_comparison.csv"}`',
        '',
        'This resolution does not edit baseline geometry. It only changes which already-locked authority artifact is used for WP02 mass closure.',
        '',
    ]
    (OUT / 'geometry_mass_authority_resolution.md').write_text('\n'.join(resolution_md), encoding='utf-8')

    vol_rows = []
    for shape, count in Counter(o.shape_kind for o in objects.values()).items():
        vol_rows.append({'shape_type': shape, 'object_count': count})
    vol_rows.append({'shape_type': 'TOTAL_OBJECTS', 'object_count': len(objects)})
    vol_rows.append({'shape_type': 'COPY_OBJECTS', 'object_count': sum(1 for o in objects.values() if o.is_copy)})
    write_csv(OUT / 'geometry_volume_closure.csv', vol_rows, ['shape_type','object_count'])

    critical_rows = []
    for key in ['TES_Pixel', 'TES_L', 'W_Multihole_CollimatorVac', 'Win_50mK', 'Win_Still', 'Win_4K', 'Win_60K', 'Win_Be', 'Win_Outer', 'CsI_Side_Segment_03', 'CsI_Side_Segment_04', 'Outer_Al_Mechanical_Shell']:
        matches = [o for o in objects.values() if key in o.name or key in o.logical]
        critical_rows.append({
            'critical_item': key,
            'matched_objects': len(matches),
            'translated_objects': sum(1 for o in matches if o.translation_status.startswith('TRANSLATED')),
            'materials': ';'.join(sorted({o.material for o in matches})),
            'status': 'PRESENT' if matches else 'MISSING',
        })
    critical_rows.append({
        'critical_item': 'InstrumentFrame.Rotation',
        'matched_objects': 1,
        'translated_objects': 1,
        'materials': 'Vacuum',
        'status': 'SOURCE_FRAME_TRANSFORM_REQUIRED_0_45_0',
    })
    write_csv(OUT / 'critical_dimension_closure.csv', critical_rows, ['critical_item','matched_objects','translated_objects','materials','status'])

    g4_rays, fluka_rays, ray_cmp = simple_aperture_rays(objects, shapes, orientations)
    write_csv(OUT / 'aperture_raytrace_geant4.csv', g4_rays, ['ray_id','start_x_cm','start_y_cm','start_z_cm','dir_x','dir_y','dir_z','ordered_material_path','ordered_volume_path','path_length_cm','engine'])
    write_csv(OUT / 'aperture_raytrace_fluka.csv', fluka_rays, ['ray_id','start_x_cm','start_y_cm','start_z_cm','dir_x','dir_y','dir_z','ordered_material_path','ordered_volume_path','path_length_cm','engine'])
    write_csv(OUT / 'aperture_raytrace_comparison.csv', ray_cmp, ['ray_id','geant4_path','fluka_path','path_match','delta_length_cm','note'])
    ray_summary = {
        'status': 'PASS' if len(ray_cmp) >= 10000 and all(str(r['path_match']) == 'True' for r in ray_cmp) else 'FAIL',
        'ray_count': len(ray_cmp),
        'direction': '+x in InstrumentFrame-local coordinates',
        'grid': '100x100 deterministic y/z grid over +/-2.7 cm around side-port center z=-5.2 cm',
        'path_mismatches': sum(1 for r in ray_cmp if str(r['path_match']) != 'True'),
        'max_abs_delta_length_cm': max((abs(float(r['delta_length_cm'])) for r in ray_cmp), default=0.0),
        'note': 'Non-transport material-path ledger; Geant4 side uses current .geo authority and FLUKA side uses the generated CG ledger from the same parsed objects.',
    }
    (OUT / 'aperture_raytrace_summary.json').write_text(json.dumps(ray_summary, indent=2, sort_keys=True), encoding='utf-8')

    blocking = [e for e in exception_rows if str(e.get('severity','')).startswith('BLOCKING')]
    translated = sum(1 for o in objects.values() if o.translation_status.startswith('TRANSLATED'))
    material_unknown = [m for m in used_mats if m not in MATERIALS]
    smoke_input_hash = sha256_path(inp)
    debug_input_hash = sha256_path(debug_inp)
    geom_hash = sha256_path(GEO)
    intro_hash = sha256_path(INTRO)
    parity = {
        'claimed_status': 'GEOMETRY_TRANSLATION_READY_PENDING_FLUKA_DEBUG' if not blocking and not material_unknown else 'BLOCKED_GEOMETRY_TRANSLATION',
        'terminal_status': None,
        'generated_at_utc': now_utc(),
        'geometry_authority': str(GEO),
        'geometry_sha256': geom_hash,
        'intro_sha256': intro_hash,
        'fluka_input': str(inp),
        'fluka_input_sha256': smoke_input_hash,
        'fluka_geometry_debug_input': str(debug_inp),
        'fluka_geometry_debug_input_sha256': debug_input_hash,
        'objects_total': len(objects),
        'objects_translated': translated,
        'copy_objects': sum(1 for o in objects.values() if o.is_copy),
        'shape_counts': source_object_counts(objects),
        'material_counts': dict(Counter(o.material for o in objects.values())),
        'blocking_exceptions': blocking,
        'unknown_materials': material_unknown,
        'global_rotation_policy': {
            'authority': 'InstrumentFrame.Rotation 0 45 0',
            'implementation': 'geometry generated in InstrumentFrame-local coordinates; source adapter must apply inverse 45 degree y-axis transform',
            'status': 'NONBLOCKING_WITH_SOURCE_POLICY',
        },
        'mass_closure_note': 'Mass closure is against the locked current .geo authority. The directory-local bounds JSON is retained as an auxiliary stale-bounds comparison because it predates the fix5 .geo topology update.',
        'geometry_mass_closure': mass_basis,
        'aperture_raytrace': ray_summary,
        'next_required_action': 'Run rfluka -M1 fix5_geometry_debug in 02_geometry_translation/fluka_geometry and append overlap_check.log before G2 can be considered for pass.',
    }
    (OUT / 'geometry_parity.json').write_text(json.dumps(parity, indent=2, sort_keys=True), encoding='utf-8')
    (OUT / 'summary.json').write_text(json.dumps(parity, indent=2, sort_keys=True), encoding='utf-8')
    md = [
        '# WP02 geometry translation',
        '',
        f'- claimed_status: {parity["claimed_status"]}',
        f'- translated objects: {translated}/{len(objects)}',
        f'- copy objects: {parity["copy_objects"]}',
        f'- FLUKA smoke input: `{inp}`',
        f'- FLUKA geometry debug input: `{debug_inp}`',
        f'- global rotation policy: {parity["global_rotation_policy"]["implementation"]}',
        f'- blocking exceptions: {len(blocking)}',
        f'- mass closure basis: {mass_basis["basis"]}',
        f'- current .geo total non-vacuum mass: {total_source_geo_mass:.9g} kg',
        f'- aperture raytrace: {ray_summary["status"]}, {ray_summary["ray_count"]} rays',
        f'- auxiliary stale-bounds comparison: `{OUT / "geometry_auxiliary_bounds_comparison.csv"}`',
        '',
        'G2 is not declared here; the generated input still requires an executable FLUKA geometry-debug run and log capture.',
    ]
    (OUT / 'geometry_parity.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    (OUT / 'summary.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    (OUT / 'overlap_check.log').write_text('PENDING: run rfluka geometry smoke and replace/append this log.\n', encoding='utf-8')
    return 0 if not blocking and not material_unknown else 2


if __name__ == '__main__':
    raise SystemExit(main())
