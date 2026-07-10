# Post-Deploy Checklist — WorkSearcher VPS

Checklist de verificación después del primer deploy. Mantener al lado del teléfono.

> **Antes de usar:** reemplazá `<your-vps-ip>` con la IP real de tu instancia (Vultr dashboard → Overview).

---

## PRIORIDAD 1 · Hoy, antes de buscar trabajo (5 min)

### 1A · 2FA en Vultr

- [ ] Andá a https://my.vultr.com → Account → 2FA
- [ ] Activar TOTP con Authy o Google Authenticator
- [ ] Guardar códigos de respaldo en lugar seguro

**Por qué importa:** sin 2FA, password de email comprometida = VPS perdido. Es el único item que no se puede recuperar.

### 1B · Verificar que el cron anda

```bash
ssh deploy@<your-vps-ip>
sudo tail -20 /var/log/worksearcher.log
```

- [ ] Líneas de las últimas 4h visibles → todo bien
- [ ] Líneas de hace 20h+ + "No module named worksearcher" → bug conocido, ver fix abajo

**Si falla el cron (bug `No module named worksearcher`):**

Causa raíz: `uv run` no instala el paquete `worksearcher` local en el venv — pyproject.toml no tiene sección `[build-system]`, así que uv solo instala las dependencias pip (jobspy, playwright) pero no el código de la app. El venv queda sin el módulo `worksearcher` y `python -m worksearcher` falla.

```bash
sudo -u worksearcher bash -c "(crontab -l 2>/dev/null | grep -v 'worksearcher run'; echo '0 */4 * * * HOME=/var/lib/worksearcher cd /opt/worksearcher && /opt/worksearcher/.venv/bin/python -m worksearcher run >> /var/log/worksearcher.log 2>&1') | crontab - && crontab -l"
```

Cambio clave: usar `/opt/worksearcher/.venv/bin/python` directamente, no `uv run python`. Como worksearcher es owner de /opt/worksearcher, Python encuentra el módulo en el cwd.

### 1C · Deshabilitar fail2ban (temporal)

fail2ban se autobaneó tu IP. Hasta arreglar bien:

```bash
sudo systemctl disable --now fail2ban
```

No es crítico para el job search. Lo reactivamos cuando esté bien configurado.

---

## PRIORIDAD 2 · Esta semana (10 min)

### 2A · Fix `harden.sh` en el repo ✅ Resuelto

Ambos bugs ya corregidos en `deploy/harden.sh`: drop-in instala como
`00-worksearcher.conf` (carga antes que `50-cloud-init.conf`), y el script crea
el usuario `deploy` con sudo NOPASSWD + `authorized_keys` copiada ANTES de
aplicar `PermitRootLogin no`. Ver ADR-006 addendum en `docs/contexto/decisiones.md`.

---

## PRIORIDAD 3 · Cuando puedas (1-2 días)

### 3A · jobspy local ✅ Resuelto

Bug: `Invalid country string: 'sri lanka'` / `'cameroon'`. El local pass pasaba
`location="Celaya, Guanajuato"` con `is_remote=False`, jobspy intentaba
parsear como país y fallaba de forma no-determinista.

**Fix aplicado:** `worksearcher/scrapers/jobspy_scraper.py` pasa
`country="mexico"` explícito en el local pass. Cubierto por
`test_jobspy_local_pass_passes_country_mexico`. Ver ADR-006 addendum v2 (Bug F)
en `docs/contexto/decisiones.md`.

### 3B · OCC (occ.com.mx)

Probable geo-block. 0 jobs scrapeados. Investigar con browser abierto a mano qué pasa. Quizás requiere cambiar user-agent o agregar cookies.

### 3C · Bumeran / Computrabajo parciales

Algunos términos devuelven "no job cards loaded". Anti-bot. La doc dice que Vultr Mexico City reduce este problema, pero hay términos específicos que siguen fallando. Aceptable como está.

---

## Verificaciones semanales (5 min)

```bash
ssh deploy@<your-vps-ip>

# 1. Último log
sudo tail -30 /var/log/worksearcher.log

# 2. DB stats
sqlite3 /var/lib/worksearcher/worksearcher.db "SELECT COUNT(*) FROM jobs WHERE notified=0"
# Esperado: bajo (jobs viejos ya enviados, nuevos llegan y se notifican)

# 3. Disko
df -h / | tail -1
# Esperado: <50% usado

# 4. UFW status
sudo ufw status | head -10

# 5. Cron
sudo -u worksearcher crontab -l

# 6. Memory
free -h | head -2
```

---

## Recovery procedures

### Si te banean (fail2ban) o perdés SSH

1. Vultr dashboard → tu server → "View Console" (noVNC en browser)
2. Logueás como root (Vultr tiene la password o podés resetearla)
3. Desde ahí: `systemctl disable --now fail2ban` (si aplica)
4. O: `rm /etc/ssh/sshd_config.d/00-worksearcher.conf && systemctl reload ssh` (revierte hardening)

### Si la app no anda pero SSH sí

```bash
sudo -u worksearcher bash -c "cd /opt/worksearcher && /opt/worksearcher/.venv/bin/python -m worksearcher run"
```

Mirá la salida. Si falla, el log te dice qué scraper.

### Si todo se rompe, último recurso

Vultr dashboard → trash icon → VPS destruido. Re-deploy desde cero (15 min). Perdés la DB (jobs vistos), rehacés .env, redesployás código.

---

## Lo que NO voy a hacer

- Tocar el repo `main` sin tu OK
- Forzar fixes a scrapers que no son blockers
- Re-activar fail2ban hasta que esté bien configurado
- Cambiar la arquitectura (SQLite, cron, Meta API)

---

## Contactos / info (reemplazar antes de commitear)

- **VPS IP:** `<your-vps-ip>`
- **Vultr region:** Mexico City
- **Repo:** github.com/JuanP-a/WorkSearcher
- **Meta API:** tokens en `.env` (revisar que no estén commiteados)
- **Service user:** worksearcher (cron, app)
- **SSH user:** deploy (recovery)
- **Root:** solo via Vultr web console
