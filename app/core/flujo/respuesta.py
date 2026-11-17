"""LAS CITAS: CADA FILA, REGLA, ENVIO, CANTIDAD Y "NO VENDEMOS" CON SU NUMERO (5-nov-2026, FICHA 88).

Lo que queda de la respuesta atada de la FICHA 90 despues de archivar el agente, 17-nov, orden de Martin: los numeros con
que el buscador y la tabla citan lo que devuelven. Armar la respuesta con esos numeros lo hacia el agente; ahora la arma
el flujo nuevo, `app/core/flujo/nuevo/`. Lo demas esta en git, para volver con git revert.
"""


class Citas:
    """LO QUE EL MODELO PUEDE CITAR EN EL TURNO, 5-nov, FICHA 88 arreglo 1: cada fila, regla, envio, cantidad y "no
    vendemos" que devolvio una herramienta lleva un numero, P1, R1, E1, N1, D1, y la respuesta solo cita esos numeros. Lo
    que no vino de una herramienta en este turno no tiene numero, y no se puede decir."""
    LETRA = {"producto": "P", "regla": "R", "envio": "E", "no_vendemos": "N", "dato": "D"}

    def __init__(self):
        self.items: dict = {}

    def __call__(self, tipo: str, clave: str, texto: str = "") -> str:
        for k, (t, c, _) in self.items.items():
            if (t, c) == (tipo, clave):
                return k
        k = f"{self.LETRA[tipo]}{sum(1 for x in self.items if x[0] == self.LETRA[tipo]) + 1}"
        self.items[k] = (tipo, clave, texto)
        return k

    def producto(self, pid: str) -> str:
        return self("producto", pid)
