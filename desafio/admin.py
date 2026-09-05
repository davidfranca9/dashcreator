from django.contrib import admin
from django.db.models import Sum

from .models import CheckIn, Comentario, Conclusao, Missao, Participante, PontoEvento, Post


@admin.register(Participante)
class ParticipanteAdmin(admin.ModelAdmin):
    list_display = ("nome", "email", "whatsapp", "instagram", "codigo_acesso", "total_pontos", "ativa", "created_at")
    list_filter = ("ativa",)
    search_fields = ("nome", "email", "whatsapp", "instagram", "codigo_acesso")
    readonly_fields = ("codigo_acesso",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_total=Sum("pontos__pontos"))

    @admin.display(description="Pontos", ordering="_total")
    def total_pontos(self, obj):
        return obj._total or 0


@admin.register(Missao)
class MissaoAdmin(admin.ModelAdmin):
    list_display = ("dia", "titulo", "data_liberacao")
    ordering = ("dia",)


@admin.register(Conclusao)
class ConclusaoAdmin(admin.ModelAdmin):
    list_display = ("participante", "missao", "concluida_em", "no_prazo", "tem_comprovacao")
    list_filter = ("missao",)
    search_fields = ("participante__nome", "participante__email")

    @admin.display(boolean=True, description="No prazo")
    def no_prazo(self, obj):
        return obj.no_prazo

    @admin.display(boolean=True, description="Comprovou")
    def tem_comprovacao(self, obj):
        return obj.tem_comprovacao


@admin.register(PontoEvento)
class PontoEventoAdmin(admin.ModelAdmin):
    list_display = ("participante", "tipo", "pontos", "referencia", "created_at")
    list_filter = ("tipo",)
    search_fields = ("participante__nome", "participante__email")


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("participante", "texto", "created_at")
    search_fields = ("participante__nome", "texto")


@admin.register(Comentario)
class ComentarioAdmin(admin.ModelAdmin):
    list_display = ("participante", "post", "created_at")
    search_fields = ("participante__nome", "texto")


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ("participante", "data")
    list_filter = ("data",)
