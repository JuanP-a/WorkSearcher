# fix-012: Filtrar por título "Senior" cuando no hay años explícitos

## 1. Propósito
`meets_experience_requirement` sólo detecta años de experiencia mencionados explícitamente
en título/descripción (`extract_min_years_required`). Un job titulado "Senior Backend
Engineer" sin ningún número de años en el texto retorna `min_years=None` →
`meets_experience_requirement` asume "accesible" y lo deja pasar, aunque el usuario tenga
`MAX_YEARS_EXPERIENCE=3`. Esto contamina las notificaciones con roles senior que el
usuario no puede cumplir.

## 2. Comportamiento esperado
- Nueva función `title_implies_senior(title: str) -> bool` — matchea patrones de
  seniority en el **título únicamente** (no en la descripción, para evitar falsos
  positivos de frases como "collaborate with senior engineers" en el cuerpo).
- Patrón cubre EN + ES: `senior`, `sr.`, `staff`, `principal`, `lead`, `líder`,
  `architect`/`arquitecto`, `director`, `head of`, `chief`, `vp`.
- `meets_experience_requirement`: si `extract_min_years_required` retorna `None`
  (sin años explícitos) Y `title_implies_senior(job.title)` es `True`, se asume
  un mínimo implícito de `_SENIOR_TITLE_IMPLIED_YEARS = 5` años antes de comparar
  contra `max_years`.
- Si el texto ya menciona años explícitos (con o sin título senior), esos años
  tienen prioridad — el título senior sólo aplica como fallback cuando no hay
  número explícito. Esto incluye el caso "entry-level" explícito, que sigue
  ganando (min_years=0) aunque el título diga "Senior" (caso raro pero no debe romperse).
- Sin título senior y sin años explícitos → comportamiento sin cambios (pasa el filtro).

## 3. Scope
**In**: `title_implies_senior`, cambio en `meets_experience_requirement`, tests unitarios
para ambas funciones y para `filter_jobs` con el nuevo caso.
**Out**: Detección de seniority en la descripción (fuera de scope — alto riesgo de
falsos positivos). Umbral de años implícitos configurable vía `.env` (hardcoded,
consistente con `_ENTRY_LEVEL_PATTERN` que tampoco es configurable).

## 4. Decisiones de diseño
- **Sólo título, no descripción.** La descripción menciona "senior" en contextos que
  no describen el rol mismo (colegas, cliente, etc.) con demasiada frecuencia — el
  título es la señal confiable.
- **Años explícitos siempre ganan.** Si el job dice "Senior Engineer, 2+ years", los
  2 años explícitos son más específicos que la heurística de 5 — no se sobreescribe.
- **5 años implícitos, no un mapeo por tier (staff/principal/director).** Un solo
  valor conservador es suficiente para el objetivo (excluir roles senior de un
  usuario buscando ≤3 años) sin inventar precisión que no está respaldada por datos.

## 5. Criterios de verificación
- [ ] `title_implies_senior("Senior Backend Engineer")` → `True`
- [ ] `title_implies_senior("Sr. Software Engineer")` → `True`
- [ ] `title_implies_senior("Backend Developer")` → `False`
- [ ] `title_implies_senior("Líder Técnico")` → `True`
- [ ] `meets_experience_requirement(job=Senior sin años, max_years=3)` → `False`
- [ ] `meets_experience_requirement(job=Senior sin años, max_years=5)` → `True` (5 ≤ 5)
- [ ] `meets_experience_requirement(job=Senior con "2 years" explícito, max_years=3)` → `True` (explícito gana)
- [ ] `meets_experience_requirement(job=Senior + "entry level" explícito, max_years=3)` → `True` (entry-level gana)
- [ ] `filter_jobs` excluye títulos senior sin años cuando `max_years_experience=3`
- [ ] Todos los tests existentes siguen pasando (no regresiones)
- [ ] `ruff check` + `ruff format` sin violaciones

## 6. Archivos afectados
| Acción | Archivo |
|--------|---------|
| Modify | `worksearcher/core/filters.py` |
| Modify | `tests/test_filters.py` |
| Modify | `docs/contexto/errores-conocidos.md` |
