# Saskia — Agent Messages (WhatsApp / Evolution API)

**Date:** 2026-09-02
**Audience:** Saskia (Spanish, Paraguayan voice)
**Channel:** WhatsApp via Evolution API (operator's existing `aiw-alerts-v2` instance)
**Pre-condition:** Decide Path A/B/C from `docs/operations/2026-09-02-saskia-decision-hosted-pivot.md` first.

---

## Sender / recipient setup

- **From:** AI Whisperers (operator's existing WhatsApp number)
- **To:** Saskia's confirmed WhatsApp number (per `saskia-personal-context` contact list — operator to verify)
- **Cadence:** one-time setup (3-4 messages), then reactive support only
- **Language:** Spanish (Paraguayan register; "vos" where she does, "usted" where formal)

---

## Message 1 — Initial setup announcement (one-shot, sent when hosted is live)

```
¡Hola Saskia! 👋

Tenemos todo listo para que uses el sistema. Te explico en 3 mensajes qué cambió y qué necesitás hacer.

📌 Cambio importante: en vez de instalar el sistema en tu laptop, lo tenemos en un servidor seguro. Vas a entrar con un link, sin instalar nada.

🔗 Tu link: https://saskia-rms.paragu-ai.com
👤 Usuario: saskia@paragu-ai.com
🔑 Contraseña: <OPERATOR_GENERATED>

📱 Tips:
1. Guardá el link en la pantalla de inicio de tu celular (en Chrome: ⋮ → "Agregar a pantalla de inicio")
2. La contraseña la cambiás vos después de entrar (arriba a la derecha → Mi cuenta)
3. Si no podés entrar, escribime por acá y te ayudo en el momento

¿Probás entrar y me decís si funciona? Cualquier duda, este chat.
```

**Operator action:** generate the password BEFORE sending (use `openssl rand -base64 16` or similar). Do NOT use a guessable pattern. Store in BWS as `SASKIA_USER_PASSWORD` so you can recover if she forgets.

---

## Message 2 — First-login walkthrough (sent after she confirms message 1)

```
¡Bien! Ya estás dentro 🎉

Esto es lo que vas a ver la primera vez:

📦 INICIO — el panel principal con "Stock bajo" y "Ventas del día"

📋 INVENTARIO — dónde cargás tus ingredientes (harina, azúcar, huevos...). 
   Cuándo llegues del super, entrás acá y actualizás lo que compraste.

🍰 RECETAS — cómo hacés cada producto. 
   Ya te dejé el cuaderno de HEREBUS cargado, así que no tenés que tocar mucho acá al principio.

💰 PRODUCTOS — qué vendés y a qué precio. 
   Si querés cambiar un precio, es acá.

🛒 VENTAS — cada venta que hacés durante el día. 
   Acá registrás: "Vendí 3 muffins y 1 torta" → te calcula el total y baja el stock automáticamente.

📊 EXCEL — si tenés una planilla con datos para cargar, la subís acá. 
   También podés bajar todo como Excel si querés tener tu copia.

👉 Te sugiero: entrá a INVENTARIO y agregá 1 ingrediente real (lo que tengas ahora mismo). Después vas a VENTAS y registrá 1 venta de prueba. Si algo no sale, me avisás.
```

---

## Message 3 — Daily use explanation (sent 24h later, after she's tried it once)

```
¿Cómo te fue? Si ya hiciste la prueba de ayer, ya sabés lo básico.

Tu día típico va a ser así:

🌅 MAÑANA (antes de abrir):
- INICIO para ver qué hay que preparar (el sistema te dice "stock bajo" si algo se está acabando)
- Si vas al super, anotá lo que comprás en INVENTARIO al volver

🕐 DURANTE EL DÍA:
- Cada vez que vendés algo, VENTAS → Nueva venta → elegís el producto y la cantidad
- El stock baja solo. No tenés que hacer cuentas.

🌙 NOCHE (antes de cerrar):
- INICIO te muestra las ventas del día
- Si algo no cerró bien, podés "anular" la venta (te devuelve el stock)

📱 IMPORTANTE: tu data está respaldada automáticamente todos los días. No tenés que hacer nada para los backups.

🆘 Si algo no funciona o te trabás:
- Escribime por este chat
- Ojo con la contraseña: si la olvidás, en la pantalla de login hay un botón "olvidé mi contraseña" que te manda un link al mail

¡Éxitos con la primera semana! 🚀
```

---

## Message 4 — Week 1 check-in (sent 7 days after message 3)

```
¡Hola Saskia! 

Ya pasó una semana desde que arrancaste. ¿Cómo te sentís con el sistema?

Algunas preguntas para que me cuentes:

1. ¿Lo usás todos los días o te olvidás a veces?
2. ¿Hay algo que te resulte confuso o lento?
3. ¿Te pasa que no encontrás dónde está algo?
4. ¿La pantalla de inicio te muestra lo que necesitás ver o falta info?

Cualquier cosa que me digas, aunque sea chica, me sirve para mejorar el sistema. Si todo bien, también quiero saber 😊

(Lo que no funciona o no te gusta también es valiosísimo — no te quedes callada por no quejarte)
```

---

## Reactive / support messages (use as needed)

### When she says she can't log in

```
Vamos a probarlo paso a paso:

1. ¿El link es este? → https://saskia-rms.paragu-ai.com
2. ¿Tu usuario es saskia@paragu-ai.com? (todo en minúscula)
3. Probá primero cerrar el navegador y abrir de nuevo
4. Si dice "contraseña incorrecta", usá el botón "¿Olvidaste tu contraseña?" que está abajo del formulario de login — te llega un mail para resetearla

Si nada funciona, mandame una captura de pantalla de lo que ves y lo resolvemos.
```

### When she asks "where did the data go?" / "I lost a sale"

```
Tranquila, no se perdió. Toda tu data está guardada automáticamente.

Para encontrar una venta específica:
1. Andá a VENTAS
2. Arriba a la derecha hay un buscador / filtro por fecha
3. Si no la encontrás así, mandame qué día fue y qué vendiste, y te la busco yo

(Si te pasa de borrar algo por error, NO lo volver a cargar — escribime primero, porque los backups están y se puede recuperar)
```

### When she asks "¿y si pierdo el celular?"

```
Si perdés o se te rompe el celular, tu data está segura (está en el servidor, no en tu teléfono).

Para entrar desde otro lado:
1. Cualquier celular, tablet o computadora con internet
2. Abrís el link https://saskia-rms.paragu-ai.com
3. Te logueás con tu usuario y contraseña

Si también perdés la contraseña, me escribís a este chat y te reseteo el acceso.
```

### When she asks "¿esto cuesta algo mensual?"

```
No, no tiene costo mensual. Ya está todo pago dentro del proyecto que acordamos.

El servidor donde está tu sistema tiene costo (lo pago yo), pero es muy poco y ya está cubierto. Vos no te preocupés por eso.
```

### When she asks "¿puedo confiar en que no se pierde?"

```
Sí. Tu data tiene 3 capas de respaldo:

1. El servidor principal tiene copia diaria automática
2. Hay otra copia en otro servicio (R2) que también es diaria
3. Si todo lo anterior falla, tengo un cuaderno Excel que se puede descargar cuando quieras con todo

En 2 años de operar así con otros clientes, nunca perdí data. Pero si te quedás más tranquila con una copia mensual que yo te mande por mail, decime y lo configuramos.
```

### When she wants to add a new product / recipe

```
¡Genial! Te explico:

Para un PRODUCTO nuevo (ej: "Tarta de manzana" que querés empezar a vender):
1. PRODUCTOS → "+ Nuevo producto"
2. Nombre: "Tarta de manzana"
3. Precio: lo que vas a cobrar
4. Receta: si ya la tenés cargada en RECETAS, la elegís acá. Si no, primero cargá la receta.

Para una RECETA nueva (ej: cómo hacés la torta):
1. RECETAS → "+ Nueva receta"
2. Nombre: "Torta de chocolate"
3. Cantidad que rinde (ej: 1 torta rinde 12 porciones)
4. Abajo, en INGREDIENTES, vas agregando: 200g harina, 150g azúcar, 3 huevos...
5. Cada vez que pongás un ingrediente nuevo, te lo busca en INVENTARIO. Si no existe, te pregunta si querés crearlo.

Si te trabás, mandame qué querés cargar y te ayudo.
```

---

## Operator reference: how to send these messages

**Sending via Evolution API** (your existing setup):

```python
import base64, json, urllib.request
from pathlib import Path

# Load credentials — Pattern 5 from credential-redacted-grep skill
_cfg = {}
for line in Path("/opt/data/.alert-config").read_text().splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        k, _, v = line.partition("=")
        _cfg[k.strip()] = v.strip().strip('"').strip("'")
URL = _cfg["EVOLUTION_URL"].rstrip("/")
KEY = _cfg["EVOLUTION_APIKEY"]
INST = _cfg.get("EVOLUTION_INSTANCE") or "aiw-alerts-v2"
SASKIA_NUMBER = _cfg.get("SASKIA_WHATSAPP_NUMBER") or "595XXXXXXXXX"

# Send text message
payload = {
    "number": SASKIA_NUMBER,
    "text": "<message body here>",
}
resp = json.loads(
    urllib.request.urlopen(
        urllib.request.Request(
            f"{URL}/message/sendText/{INST}",
            data=json.dumps(payload).encode(),
            headers={"apikey": KEY, "Content-Type": "application/json"},
            method="POST",
        ),
        timeout=15,
    ).read()
)
print(f"sent_message_id={(resp.get('key') or {}).get('id')}")
```

**Cadence:**
- Message 1: when hosted is live and you've verified login works
- Message 2: ~2-4 hours after message 1 (give her time to log in)
- Message 3: 24h after message 2 (give her time to try the basics)
- Message 4: 7 days after message 3 (the "round 1" check-in)
- Reactive: as needed

**Cadence rule: don't pile on.** If she's busy or stressed, space them out more. The point is "be there when she needs," not "be in her face."

---

## What NOT to do

- ❌ Don't send her a long manual in one message — she'll ignore it
- ❌ Don't send technical language ("DATABASE_URL", "Neon", "Render") — she'll be confused
- ❌ Don't ask for her feedback on things she hasn't seen yet
- ❌ Don't pile up questions in one message (one question at a time is more effective)
- ❌ Don't send messages between 21:00 and 08:00 her local time (Paraguay, UTC-4)
- ✅ Do use her name ("Saskia") not "estimada" or formalities
- ✅ Do use Spanish Paraguayan register ("vos" if she does, "tenés", "querés")
- ✅ Do keep messages short — she'll read them
- ✅ Do include one emoji per message — friendly but not childish
- ✅ Do end with a question or call-to-action — invites response

---

## Template variables

These should be filled in by operator before sending:

| Variable | Where it comes from | Example |
|---|---|---|
| `<OPERATOR_GENERATED>` | Password generated by operator (BWS: `SASKIA_USER_PASSWORD`) | `T8k#mP2xQ9vR` |
| `<SASKIA_NUMBER>` | Saskia's confirmed WhatsApp number | `595981324569` (E.164 format, no +) |
| `<URL>` | The hosted URL once deployed | `https://saskia-rms.paragu-ai.com` |

The URL placeholder is `saskia-rms.paragu-ai.com` based on the operator's last decision ("irl under something.paragu-ai.com" per `20260901_143429_48eef3` session message 17822). Replace if operator picks a different domain.