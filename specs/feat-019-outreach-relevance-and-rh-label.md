# feat-019: Filtro de relevancia + etiqueta de confirmación RH en outreach

## 1. Propósito
El primer run en producción (radio 80km, Celaya/Guanajuato) mostró dos problemas
de calidad de datos frente al propósito de WorkSearcher (buscador para un perfil
de sistemas/ciberseguridad):

1. **Sin filtro de rubro**: Overpass trae cualquier negocio con tag `website`
   (hoteles, escuelas, gobierno, retail) sin relación con necesidad de TI/dev.
2. **Correo sin distinguir confiabilidad**: de 5 empresas notificadas, ninguna
   tenía un correo de RH real — todas cayeron al fallback genérico
   (`reserve@`, `contacto.enlinea@`, `info@`, un nombre personal). El campo
   `email_is_hr_context` ya existe en el modelo pero no se muestra en el
   mensaje de WhatsApp, así que el usuario no puede distinguir un correo
   confirmado de RH de una adivinanza.

## 2. Comportamiento esperado
- **Filtro de relevancia**: durante el mismo crawl que ya hace
  `extract_email()` (home + rutas de contacto), se revisa el texto de las
  páginas obtenidas contra `OUTREACH_RELEVANCE_KEYWORDS` (config CSV, mismo
  patrón case-insensitive/substring que `SEARCH_KEYWORDS` de jobs). Si ninguna
  página contiene alguna keyword, la empresa se descarta — no se persiste ni
  se notifica (mismo patrón que `filter_jobs`: lo irrelevante no llega a la
  DB, no se "guarda para revisar después").
- Empresas que fallan el crawl completo (todas las rutas fallan) se tratan
  como no-relevantes (no hay texto para evaluar) y se descartan igual que
  hoy se descartan por `no_email_found` — no se persisten.
- **Etiqueta RH en el digest**: `_build_outreach_message` antepone
  `✅ RH confirmado` cuando `email_is_hr_context=True`, o
  `⚠️ contacto general` cuando es `False`, a cada línea de empresa.

## 3. Scope
**In**: campo `OUTREACH_RELEVANCE_KEYWORDS` en `Settings`, extensión de
`extract_email()` para evaluar relevancia sobre el mismo HTML ya crawleado,
filtro en `run_outreach_pipeline` que descarta no-relevantes antes de
persistir, etiqueta RH/general en `_build_outreach_message`.

**Out**: NLP o scoring de relevancia más allá de substring case-insensitive
(mismo tradeoff ya aceptado en `filters.py` para jobs — ej. "sistemas" podría
matchear falsos positivos, aceptado por simplicidad). Reintentos de
extracción para empresas ya descartadas por no-relevancia (quedan fuera para
siempre, igual que `no_email_found` — ver limitación conocida ya documentada
en `errores-conocidos.md`). Clasificación de industria/rubro estructurada.

## 4. Decisiones de diseño
- **Relevancia se evalúa sobre el HTML ya crawleado, sin requests extra.**
  `extract_email()` ya descarga home + rutas de contacto buscando `mailto:`;
  reutilizar ese mismo contenido para el chequeo de keywords evita duplicar
  crawl (que ya es el costo dominante del pipeline, visible en el primer run
  de producción).
- **Descartar, no solo etiquetar, lo no-relevante.** Sigue el mismo patrón que
  `filter_jobs`/`is_relevant` para `Job` — lo que no matchea keywords no se
  guarda en absoluto. Alternativa considerada (guardar todo con un flag
  `relevant` y filtrar solo en el mensaje) se descartó: acumular en DB negocios
  irrelevantes (hoteles, escuelas) para siempre no aporta valor y ensucia la
  tabla `companies` sin un caso de uso claro para revisarlos después.
- **Etiqueta RH reusa el campo `email_is_hr_context` ya existente** — no
  requiere nueva heurística, solo exponer un dato ya calculado que no se
  mostraba.

## 5. Criterios de verificación
- [ ] `Settings().outreach_relevance_keywords_list` tiene default no vacío
      (ej. sistemas, tecnologia, desarrollo, software, ti, digital, etc.)
- [ ] `extract_email()` con HTML que menciona una keyword de relevancia
      retorna una empresa considerada relevante (no descartada)
- [ ] `extract_email()` con HTML sin ninguna keyword de relevancia en
      ninguna página crawleada resulta en la empresa descartada por el
      pipeline (no persistida, no notificada)
- [ ] El pipeline no hace requests HTTP adicionales por el chequeo de
      relevancia (se verifica contando llamadas mockeadas en el test)
- [ ] `_build_outreach_message` con una empresa `email_is_hr_context=True`
      incluye "RH confirmado"; con `False` incluye "contacto general"
- [ ] Todos los tests existentes siguen pasando (no regresiones)
- [ ] `ruff check` + `ruff format` sin violaciones

## 6. Archivos afectados
| Acción | Archivo |
|--------|---------|
| Modify | `worksearcher/config.py` (`OUTREACH_RELEVANCE_KEYWORDS`) |
| Modify | `worksearcher/outreach/email_extractor.py` (chequeo de relevancia) |
| Modify | `worksearcher/outreach/pipeline.py` (descartar no-relevantes) |
| Modify | `worksearcher/notifier/whatsapp.py` (etiqueta RH/general) |
| Modify | `.env.example` |
| Modify | `tests/conftest.py`, `tests/test_config.py`, `tests/test_outreach.py`, `tests/test_whatsapp.py` |
