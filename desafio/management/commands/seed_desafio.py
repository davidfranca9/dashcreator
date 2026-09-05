"""Cadastra as 7 missoes do Desafio Postaria Mais (14/09 a 20/09).

Idempotente: pode rodar quantas vezes quiser, atualiza titulo/data no lugar
de duplicar. As datas batem com as usadas no frontend
(landing/desafio/dashboard-missions.html).
"""

from datetime import date

from django.core.management.base import BaseCommand

from desafio.models import Missao

MISSOES = [
    (1, "Arrumando a casa", date(2026, 9, 14)),
    (2, "Construção de Intenção", date(2026, 9, 15)),
    (3, "Construindo Conexão", date(2026, 9, 16)),
    (4, "Levantando Bandeiras", date(2026, 9, 17)),
    (5, "Condução dos seus processos", date(2026, 9, 18)),
    (6, "Atração Qualificada", date(2026, 9, 19)),
    (7, "A Grande Oferta", date(2026, 9, 20)),
]


class Command(BaseCommand):
    help = "Cria/atualiza as 7 missoes do Desafio Postaria Mais."

    def handle(self, *args, **options):
        for dia, titulo, data_liberacao in MISSOES:
            missao, criada = Missao.objects.update_or_create(
                dia=dia,
                defaults={"titulo": titulo, "data_liberacao": data_liberacao},
            )
            verbo = "criada" if criada else "atualizada"
            self.stdout.write(f"Dia {dia:02d} ({data_liberacao:%d/%m}) {missao.titulo}: {verbo}")
        self.stdout.write(self.style.SUCCESS(f"{len(MISSOES)} missoes prontas."))
