"""Motor privado de asignaciones para un intercambio de regalos.

No imprime, guarda ni registra los emparejamientos. El programa principal
solo los conserva temporalmente en su sesión hasta enviar los mensajes.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
import secrets
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class Participante:
    familia: str
    nombre: str
    correo: str


_CORREO_RE = re.compile(r"^[^\s@<>;,]+@[^\s@<>;,]+\.[^\s@<>;,]{2,}$")


def validar_participantes(filas: Sequence[Mapping[str, object]]) -> tuple[list[Participante], list[str]]:
    """Normaliza filas, descarta filas completamente vacías y devuelve errores."""
    personas: list[Participante] = []
    errores: list[str] = []
    vistos: set[str] = set()

    for numero, fila in enumerate(filas, start=2):
        familia = str(fila.get("familia") or "").strip()
        nombre = str(fila.get("nombre") or "").strip()
        correo = str(fila.get("correo") or "").strip()

        if not (familia or nombre or correo):
            continue
        if not familia or not nombre or not correo:
            errores.append(f"Fila {numero}: debes completar familia, nombre y correo.")
            continue
        if any("\n" in campo or "\r" in campo for campo in (familia, nombre, correo)):
            errores.append(f"Fila {numero}: los datos no pueden contener saltos de línea.")
            continue
        if not _CORREO_RE.fullmatch(correo) or len(correo) > 254:
            errores.append(f"Fila {numero}: el correo no tiene un formato válido.")
            continue
        if correo.casefold() in vistos:
            errores.append(f"Fila {numero}: el correo ya aparece en otra fila.")
            continue
        vistos.add(correo.casefold())
        personas.append(Participante(familia=familia, nombre=nombre, correo=correo))

    if not errores:
        if len(personas) < 2:
            errores.append("Debes registrar al menos dos participantes.")
        else:
            conteo = Counter(p.familia.casefold() for p in personas)
            if len(conteo) < 2:
                errores.append("Se necesitan participantes de al menos dos familias diferentes.")
            for familia_normalizada, cantidad in conteo.items():
                if 2 * cantidad > len(personas):
                    nombre_familia = next(p.familia for p in personas if p.familia.casefold() == familia_normalizada)
                    errores.append(
                        f"No es posible sortear: {nombre_familia} tiene {cantidad} de "
                        f"{len(personas)} integrantes. Ninguna familia puede superar la mitad."
                    )
    return personas, errores


def sortear(personas: Sequence[Participante]) -> dict[int, int]:
    """Devuelve {índice_de_quien_regala: índice_de_quien_recibe}.

    Emparejamiento bipartito con caminos aumentantes y orden aleatorio
    criptográficamente seguro. Para un conjunto válido encuentra una
    biyección sin destinatarios de la propia familia, sin usar reintentos
    aleatorios indefinidos.

    La distribución no es necesariamente uniforme entre los sorteos válidos.
    """
    n = len(personas)
    if n < 2:
        raise ValueError("Se requieren al menos dos participantes.")

    conteos = Counter(p.familia.casefold() for p in personas)
    if len(conteos) < 2 or max(conteos.values()) * 2 > n:
        raise ValueError("Las familias no permiten un sorteo completo sin coincidencias internas.")

    aleatorio = secrets.SystemRandom()
    familias = [p.familia.casefold() for p in personas]
    candidaturas: list[list[int]] = []
    for i in range(n):
        destinos = [j for j in range(n) if familias[i] != familias[j]]
        aleatorio.shuffle(destinos)
        candidaturas.append(destinos)

    emisores = list(range(n))
    aleatorio.shuffle(emisores)
    recibe_de: dict[int, int] = {}  # destinatario -> regalador

    def aumentar(regalador: int, visitados: set[int]) -> bool:
        for destinatario in candidaturas[regalador]:
            if destinatario in visitados:
                continue
            visitados.add(destinatario)
            anterior = recibe_de.get(destinatario)
            if anterior is None or aumentar(anterior, visitados):
                recibe_de[destinatario] = regalador
                return True
        return False

    for regalador in emisores:
        if not aumentar(regalador, set()):
            raise RuntimeError("Error al encontrar un sorteo válido; revisa los datos.")

    asignaciones = {regalador: destinatario for destinatario, regalador in recibe_de.items()}
    if not comprobar_sorteo(personas, asignaciones):
        raise RuntimeError("No se superó la comprobación interna del sorteo.")
    return asignaciones


def comprobar_sorteo(personas: Sequence[Participante], asignaciones: Mapping[int, int]) -> bool:
    """Comprueba que todos den y reciban uno, sin repeticiones ni familia propia."""
    n = len(personas)
    if set(asignaciones.keys()) != set(range(n)):
        return False
    if set(asignaciones.values()) != set(range(n)):
        return False
    return all(
        i != j and personas[i].familia.casefold() != personas[j].familia.casefold()
        for i, j in asignaciones.items()
    )
