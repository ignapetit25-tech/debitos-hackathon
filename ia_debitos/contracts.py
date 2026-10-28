"""Contratos de integración (ABCs + esquemas). Todo el dinero en centavos int.

La capa IA solo habla con el mundo mediante estos contratos. Dos
implementaciones: `synthetic` (demo, en este repo) y el adaptador real
(JSON explícito, desactivado por defecto, no verificado).
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Renglon:
    nro: int
    practica: str
    motivo: str
    facturado_cents: int
    liquidado_cents: int

    @property
    def debito_cents(self) -> int:
        return self.facturado_cents - self.liquidado_cents


@dataclass(frozen=True)
class Caso:
    id: str
    financiador: str
    factura: str
    renglones: tuple[Renglon, ...]
    total_debito_cents: int
    estado: str = "nuevo"
    fecha_prestacion: str = ""

    def validar(self) -> tuple[bool, int]:
        suma = sum(r.debito_cents for r in self.renglones)
        return suma == self.total_debito_cents, suma - self.total_debito_cents


@dataclass(frozen=True)
class Hallazgo:
    id: str
    caso_id: str
    renglon_nro: int
    tipo: str
    documento: str
    pagina: int
    fragmento: str
    interpretacion: str
    limitaciones: str = ""
    verificado: bool = False


@dataclass(frozen=True)
class ReglaRef:
    sector: str
    puntos: int  # puntaje de reglas: NO es probabilidad ni confianza
    frases: tuple[str, ...]


@dataclass(frozen=True)
class Propuesta:
    id: str
    caso_id: str
    sector: str
    regla: ReglaRef
    accion: str  # reclamar | aceptar | pedir_extension | derivar_humano
    explicacion: str
    referencias: tuple[str, ...]  # qué datos se usaron
    abstencion_clinica: bool = False
    extraccion_confianza: float = 1.0  # 0-1, concepto distinto del puntaje


@dataclass(frozen=True)
class Decision:
    propuesta_id: str
    revisor: str
    veredicto: str  # aprobada | rechazada
    nota: str = ""


@dataclass
class EventoHistorial:
    seq: int
    tipo: str  # extraccion | validacion | herramienta | llamada_modelo | propuesta | revision
    detalle: str
    antes: str = ""
    despues: str = ""
    creado: str = ""  # fecha y hora local ISO del evento


class CasoStore(abc.ABC):
    @abc.abstractmethod
    def obtener_caso(self, id: str) -> Caso: ...

    @abc.abstractmethod
    def obtener_estado_casos(self, filtros: dict | None = None) -> list[Caso]: ...

    @abc.abstractmethod
    def guardar_propuesta(self, caso_id: str, propuesta: Propuesta) -> None: ...


class ArancelService(abc.ABC):
    @abc.abstractmethod
    def consultar_arancel(
        self, prestacion: str, financiador: str, fecha: str
    ) -> dict | None: ...


class RulesService(abc.ABC):
    @abc.abstractmethod
    def evaluar_reglas(self, motivo: str) -> ReglaRef: ...
