# Sazon SeasonalEvent model — comprehensive holiday & festive-day catalog (PY + NL)

**Date:** 2026-10-12
**Author:** AIW Bot (post-OOB-2026-10-12 deep-dive)
**Sister tickets:** SASKIA-213 (placeholder replacement, shipped), SASKIA-215 (LOCATION/SEASONAL/RECIPE settings + bug fix, shipped), SASKIA-214 (per-instance config refactor, drafted)
**Target ticket:** SASKIA-216 (new — SeasonalEvent model + seed catalog)
**Sources:** see §9 (all web-cited; primary = BACN Ley 7544/2025 + Rijksoverheid.nl + MEC Resolución 2.065 + portal guaraní folklore compilations + AsunciónCity.com festival guide)

---

## 1. Why this matters now (the OOB reframe)

The 2026-10-12 OOB message said **"the website of sazon should load all of the thigns"** and clarified that **La Vaquita Holandesa is the first of many clients** (multi-tenant, not per-client instances). This re-elevates the questionnaire's §16 answers from "deferred to month 3-6" (per the pre-OOB analysis) to **must-work-for-La-Vaquita-day-1**:

- **§16.1** = "¿Semana Santa 2027?" → `si` — needs a `SeasonalEvent` row for "Semana Santa 2027"
- **§16.5** = "¿Menú estacional verano/invierno?" → `si` — needs **2 anchor events** for the summer/winter menu transitions
- **§16.6** = "¿Aviso 30 días antes?" → `si` — already wired as `seasonal.notif_lead_days` (SASKIA-215); the SeasonalEvent table must respect this lead time

The Sazon website has to **render the calendar of upcoming events** (with the lead-days lead time respected) so Saskia can plan her seasonal menu + production capacity. The catalog below is the **seed data** for that page.

**Multi-tenant implication** (per OOB): the next client (a pizzeria, a café, etc.) will have its own set of relevant holidays. The `SeasonalEvent` table must support a `country` and `relevance_tag` column so each client instance shows only the events that matter to its market. See §6 for the schema.

---

## 2. Sazon-specific business context (what should be in the catalog for La Vaquita)

| Question | Answer (from §16 questionnaire) | Calendar implication |
|---|---|---|
| Bakery? | yes (panadería, 22+ products) | All "Día del Panadero" dates, "Día de Reyes" (Rosca de Reyes), Semana Santa (Rosca de Pascua / chipa), Día de la Madre (postre), San Juan (chipá / mbejú), Navidad (pan dulce) |
| Single operator? | yes (Saskia sola, §17.1) | Cannot do big event-day rushes; need **pre-event lead time** to ramp production |
| San Lorenzo, Central? | yes (location.barrio) | **10 August** (San Lorenzo patron) + **15 August** (Asunción patron) are both local demand spikes |
| Dutch heritage? | "La Vaquita **Holandesa**" (the brand) | Speculaas = Sinterklaas-relevant (NL cultural import); inform catalog but **don't pretend the brand is Dutch retail** — this is a PY panadería with a Dutch name |
| Solo PY shop? | yes | No online store, no franchises, no events. Catalog = local + sectoral + cultural, not international commerce. |

**Implication**: the default seed catalog for La Vaquita should include PY national holidays, PY commercial days (Madre/Niño/Padre/Amigo), Catholic movable feasts (Easter-dependent), school calendar (vacaciones de invierno), and the San Lorenzo + Asunción local patronales. The NL holidays (Koningsdag, Sinterklaas) are **informational** (Speculaas sells at Christmas, not Sinterklaas; the brand is symbolic), and can be included with a `low` impact tag so they show up but don't drive production.

---

## 3. Paraguay calendar — legal holidays (per Ley 7544/2025)

**Source**: Ley Nº 7544/2025 (BACN — Biblioteca y Archivo Central del Congreso, promulgada 3 September 2025). This law repealed Ley 8/90 and its amendments (715/95, 1601/00, 1723/01, 4531/11). Read 2026-10-12 from the BACN PDF.

The law fixes **13 national holidays** per year. Four are "móviles" (can be moved to the adjacent Monday by Executive decree each year). Up to **3 additional** feriados can be added by decree per year for tourism/economic/special-event reasons.

### 3.1 The 13 fixed holidays

| # | Date | Spanish name | English name | Type | Movable? |
|---|---|---|---|---|---|
| 1 | 1 January | Año Nuevo | New Year's Day | Legal | No |
| 2 | 1 March | Día de los Héroes de la Patria | Heroes' Day | Legal | **Yes** |
| 3 | Holy Thursday (movable) | Jueves Santo | Maundy Thursday | Legal | Computus |
| 4 | Good Friday (movable) | Viernes Santo | Good Friday | Legal | Computus |
| 5 | 1 May | Día de los Trabajadores | Workers' Day | Legal | No |
| 6 | 14 May | Día de la Independencia Nacional | Independence Day (eve) | Legal | No |
| 7 | 15 May | Independencia Nacional + Día de la Madre | Independence Day (day 2) | Legal | No (but the 15th is **also** Mother's Day, fixed since 1924) |
| 8 | 12 June | Día de la Paz del Chaco | Chaco Armistice | Legal | **Yes** |
| 9 | 20 June | Día de la Jura de la Constitución Nacional | Constitution Oath Day (new 2025) | Legal | **Yes** |
| 10 | 15 August | Fundación de Asunción (Asunción's patron) | Founding of Asunción | Legal | No (also Virgin of Asunción) |
| 11 | 29 September | Día de la Batalla de Boquerón | Boquerón Battle | Legal | **Yes** |
| 12 | 8 December | Día de la Virgen de Caacupé | Virgin of Caacupé (national patron) | Legal | No |
| 13 | 25 December | Navidad | Christmas | Legal | No |

### 3.2 The 2026-2027-2028 calendar (baked dates)

| Feriado | 2026 | 2027 | 2028 |
|---|---|---|---|
| Año Nuevo | jue 1 ene | vie 1 ene | sáb 1 ene |
| Héroes de la Patria | dom 1 mar → **lun 2 mar** (trasladado por Decreto 5508) | lun 1 mar (ya es lunes) | mié 1 mar |
| Jueves Santo | jue 2 abr | jue 25 mar | jue 13 abr |
| Viernes Santo | vie 3 abr | vie 26 mar | vie 14 abr |
| Día del Trabajador | vie 1 may | sáb 1 may | lun 1 may |
| Independencia (eve) | jue 14 may | vie 14 may | dom 14 may |
| Independencia (Madre) | vie 15 may | **sáb 15 may** (fiesta + feriado) | lun 15 may |
| Paz del Chaco | vie 12 jun | sáb 12 jun (puede moverse) | lun 12 jun |
| Jura de la Constitución | sáb 20 jun → **lun 22 jun** (trasladado por Decreto 6215) | dom 20 jun (puede moverse) | mar 20 jun |
| Fundación de Asunción | sáb 15 ago | dom 15 ago | mar 15 ago |
| Batalla de Boquerón | mar 29 sep (sin trasladar, decreto pendiente) | mié 29 sep (puede moverse) | vie 29 sep |
| Virgen de Caacupé | mar 8 dic | mié 8 dic | vie 8 dic |
| Navidad | vie 25 dic | sáb 25 dic | lun 25 dic |

### 3.3 Ad-hoc 2026 additional feriados (already decreed)

- **30 June 2026** — Decreto 6280/2026 declared this a one-off national feriado for Paraguay's round-of-16 World Cup qualification (Albirroja beat Germany on penalties). Future World Cup final (19 Jul 2026) may trigger more.
- **2027**: up to 3 additional feriados can still be added by decree before the year begins (Art. 4 Ley 7544/2025). Catalog must allow these.

**Source URLs** (all retrieved 2026-10-12):
- `https://www.bacn.gov.py/leyes-paraguayas/12908/ley-n-7544-2025-que-determina-los-feriados-nacionales-de-la-rep-blica-del-paraguay...` (official text)
- `https://latamref.dev/py/public-holidays` (verified 2026-07-30 against BACN)
- `https://bestparaguay.com/es/vivir/feriados-en-paraguay/` (read 2026-10-07)
- `https://www.calendarioparaguay.com/calendario-2027.html` (verified)
- `https://pytagua.com/en/paraguay-public-holidays/` (English summary)

---

## 4. Paraguay calendar — commercial / festive days (non-legal but commerce-driving)

**Source**: Tiendli.com 2026 calendar + expertosnegociosonline.com 2027 calendar + Fenicio eCommerce calendar (PDF, 2026-07-15 update) + asuncioncity.com festival guide. These are the dates that drive **retail / bakery / restaurant** demand and that operators like Saskia plan production around.

### 4.1 The PY commercial calendar (baked 2026/2027/2028)

| Event | Type | Date rule | 2026 | 2027 | 2028 | Demand signal for La Vaquita |
|---|---|---|---|---|---|---|
| **Día de Reyes / Epifanía** | Religious-cultural + commercial | Fixed 6 January | mar 6 ene | mié 6 ene | jue 6 ene | **HIGH** — Rosca de Reyes is the top-selling bakery product that week |
| **Carnaval Encarnaceno** | Regional festival | 5 Saturdays Jan-mid-Feb | 17/24/31 ene + 7/14 feb (Edición 100) | 16/23/30 ene + 6/13 feb | 15/22/29 ene + 5/12 feb | LOW (Encarnación, 380 km from Asunción) |
| **Día de San Valentín** | Commercial | Fixed 14 February | sáb 14 feb | dom 14 feb | lun 14 feb | MEDIUM (chocolates, decorated pastries) |
| **Inicio de clases PY** | School calendar | Per MEC resolución (mid-late Feb) | lun 23 feb (Res. 2.065) | estimado lun 22 feb | estimado lun 21 feb | **HIGH** — school snack orders resume (galletas, facturas) |
| **Día Internacional de la Mujer** | Commercial | Fixed 8 March | dom 8 mar | lun 8 mar | mié 8 mar | MEDIUM (cupcakes, decorated cakes) |
| **Cuaresma** (Lent) | Religious (40 days before Easter) | Ash Wednesday is Easter - 46 days | mié 18 feb (Easter 5 abr) | mié 10 feb (Easter 28 mar) | mié 23 feb (Easter 16 abr) | MEDIUM (chipa, empanada de Cuaresma; no meat Fridays push fish empanadas) |
| **Semana Santa / Pascua** | Religious (PY's biggest Christian holiday) | Maundy Thursday + Good Friday = Easter -3/-2 days | jue 2 abr + vie 3 abr | jue 25 mar + vie 26 mar | jue 13 abr + vie 14 abr | **HIGH** — Rosca de Pascua, chipa, mbejú, 12 variedades de pan dulce; orders start 2 weeks before |
| **Pascua (Easter Sunday)** | Religious | Easter Sunday | dom 5 abr | dom 28 mar | dom 16 abr | **HIGH** — Rosca de Pascua, decorated eggs (chocolate), pastelitos |
| **CyberDay Paraguay** | E-commerce (CAPACE + MIC) | First week of November (announced) | lun 2 - mié 4 nov | estimado primeros de nov (sin anunciar) | estimado primeros de nov | LOW (no online store per §21.4) but informational |
| **Día del Maestro** | School sector | Fixed 30 April | jue 30 abr | vie 30 abr | dom 30 abr | MEDIUM (gifts for teachers from parents) |
| **Día de la Madre PY** | Commercial (BIGGEST) | **Fixed 15 May** (coincides with Independencia, since 1924) | vie 15 may | **sáb 15 may** | lun 15 may | **CRITICAL** — biggest commercial event of the year, baked goods + decorated cakes; orders 7-10 days lead |
| **Día del Padre PY** | Commercial | 3rd Sunday of June (per project: would move to 16 June, not yet law) | dom 21 jun | dom 20 jun (coincide con Jura de la Constitución, new 2025) | dom 18 jun | MEDIUM (postres, decorated cakes) |
| **San Juan Ára** | Folk-cultural (PY unique) | Eve + day 23-24 June | mar 23 + mié 24 jun | mié 23 + jue 24 jun | vie 23 + sáb 24 jun | **HIGH for chipá / mbejú** (the iconic San Juan foods are exactly what La Vaquita bakes) |
| **Inicio de vacaciones de invierno PY** | School calendar | Second Monday of July (since 2023; MEC fix) | lun 13 jul | lun 12 jul (estimado) | lun 10 jul (estimado) | MEDIUM (galletas de viaje, facturas) |
| **Fin de vacaciones de invierno PY** | School calendar | 2 weeks later (Friday) | vie 24 jul | vie 23 jul (estimado) | vie 21 jul (estimado) | LOW |
| **Día del Amigo PY** | Commercial (invented in PY 1958) | Fixed 30 July | jue 30 jul | vie 30 jul | dom 30 jul | **HIGH** — low-ticket, last-minute; Pa˝ dulces, boxes, gift packaging |
| **San Lorenzo patron (district)** | Local (Saskia's district!) | Fixed 10 August | lun 10 ago | mar 10 ago | jue 10 ago | **HIGH** — local demand spike; pastelitos, empanadas, facturas |
| **Día del Niño PY** | Commercial | Fixed 16 August (since the Acosta Ñu battle) | dom 16 ago (dom) | lun 16 ago | mié 16 ago | **HIGH** — decorated cupcakes, galletas decoradas, mini cakes |
| **Primavera + Día de la Juventud** | Cultural | Fixed 21 September | lun 21 sep | mar 21 sep | jue 21 sep | LOW |
| **Black Friday Paraguay** | Global commercial (no organizer in PY) | Last Friday of November | vie 27 nov | vie 26 nov | vie 24 nov | **HIGH** (even without online store, walk-in traffic spikes on "ofertas") |
| **Halloween** | Commercial (imported) | Fixed 31 October | sáb 31 oct | dom 31 oct | mar 31 oct | LOW (not culturally PY-rooted but growing) |
| **Singles Day (11.11)** | E-commerce (imported) | Fixed 11 November | mié 11 nov | jue 11 nov | sáb 11 nov | LOW (no online store) |
| **Día de la Música PY** | Cultural | Fixed 22 November (since 1984) | dom 22 nov | lun 22 nov | mié 22 nov | LOW |
| **Día de los Pueblos Originarios** | Cultural (was "Día de la Raza") | Fixed 12 October (since 2024) | lun 12 oct | mar 12 oct | jue 12 oct | LOW (not commercially significant) |
| **Nochebuena** | Religious-cultural | Fixed 24 December | jue 24 dic | vie 24 dic | dom 24 dic | **HIGH** — pan dulce, roscón, pedidos are 5-7 days lead |
| **Año Nuevo** | Secular + religious | Fixed 31 December / 1 January | jue 31 dic | vie 31 dic | dom 31 dic | **HIGH** — pan dulce, sidra, roscón de Reyes; 7-10 days lead |
| **Día de los Almaceneros y Minoristas** | Sectoral (recent, 2026) | Fixed 8 August (since Ley 2026) | vie 8 ago | dom 8 ago | mar 8 ago | LOW (informationally relevant for the bakery's neighbors) |
| **Día del Panadero** (PY) | Sectoral (informal) | Mid-March (industry tradition, no Ley) | sin fecha oficial | sin fecha oficial | sin fecha oficial | MEDIUM (Bimbo + Copalsa run campaigns; marketing/PR opportunity) |
| **Día Nacional del Tereré** | Cultural | Last Saturday of February (SINAFOCAL) | sáb 27 feb | estimado feb | estimado feb | LOW |

### 4.2 Catholic movable feasts (Easter-dependent)

These follow the **Gregorian computus** (Easter = first Sunday after first ecclesiastical full moon on/after 21 March):

| Feast | Offset from Easter | 2026 | 2027 | 2028 |
|---|---|---|---|---|
| Ash Wednesday (Miércoles de Ceniza) | -46 | mié 18 feb | mié 10 feb | mié 23 feb |
| Palm Sunday (Domingo de Ramos) | -7 | dom 29 mar | dom 21 mar | dom 9 abr |
| Holy Thursday (Jueves Santo) | -3 | jue 2 abr | jue 25 mar | jue 13 abr |
| Good Friday (Viernes Santo) | -2 | vie 3 abr | vie 26 mar | vie 14 abr |
| Easter Sunday (Pascua) | 0 | dom 5 abr | dom 28 mar | dom 16 abr |
| Divine Mercy Sunday | +7 | dom 12 abr | dom 4 abr | dom 23 abr |
| Ascension (Ascensión) | +39 | jue 14 may | jue 6 may | jue 25 may |
| Pentecost (Pentecostés) | +49 | dom 24 may | dom 16 may | dom 4 jun |
| Corpus Christi | +60 | jue 4 jun | jue 27 may | jue 15 jun |
| Sacred Heart of Jesus (Sagrado Corazón) | +68 | vie 12 jun | vie 4 jun | vie 23 jun |
| Christ the King (Cristo Rey) | -4 (last Sun before Advent) | dom 22 nov | dom 21 nov | dom 25 nov |
| First Sunday of Advent | n/a (4th Sunday before Christmas) | dom 29 nov | dom 28 nov | dom 3 dic |

### 4.3 School calendar (MEC) — drives snack/kid demand

| Year | Inicio de clases | Vacaciones de invierno | Fin de clases | Cierre administrativo |
|---|---|---|---|---|
| 2023 | lun 20 feb (Res. 1.438) | 10-21 jul | jue 30 nov | n/a |
| 2024 | vie 23 feb (Res. 6) | 8-19 jul | vie 29 nov | n/a |
| 2025 | lun 24 feb (Res. 1.963) | 14-25 jul | vie 28 nov | n/a |
| 2026 | **lun 23 feb (Res. 2.065)** | **13-24 jul** | **lun 30 nov** | vie 11 dic (cierre) |
| 2027 | estimado lun 22 feb (sin decreto al 2026-10-07) | estimado 12-23 jul | estimado mar 30 nov | estimado vie 10 dic |
| 2028 | estimado lun 21 feb | estimado 10-21 jul | estimado jue 30 nov | estimado vie 8 dic |

**Pattern** (4-year repetition): clases start last Monday of February, vacaciones de invierno start 2nd Monday of July (always 2 weeks), clases end last business day of November, cierre first Friday of December. The 2027 calendar is **not** published as of 2026-10-07 (per Ahendu); MEC typically publishes in December.

**For La Vaquita**: inicio de clases = high demand (parents stock up galletas/facturas for lunchboxes). Vacaciones de invierno = medium demand (travel snacks). Fin de clases = low (kids at home, no lunchbox demand).

---

## 5. Netherlands calendar — legal holidays + commercial (for the "Vaquita Holandesa" heritage)

**Source**: Rijksoverheid.nl (official 2026-2027 list) + datkanikzelf.nl + timeanddate.com + nlcompass.com + amsterdamtips.com + DACHIST.org + stnicholascenter.org. Retrieved 2026-10-12.

### 5.1 The 9-11 official feestdagen (per Rijksoverheid.nl)

| # | Holiday | Dutch name | Type | 2026 | 2027 |
|---|---|---|---|---|---|
| 1 | New Year's Day | Nieuwjaarsdag | Public (paid) | jue 1 ene | vie 1 ene |
| 2 | Good Friday | Goede Vrijdag | Public (limited) — banks/ government closed but not everyone has it off | vie 3 abr | vie 26 mar |
| 3 | Easter Sunday | Eerste Paasdag | Public | dom 5 abr | dom 28 mar |
| 4 | Easter Monday | Tweede Paasdag | Public | lun 6 abr | lun 29 mar |
| 5 | King's Day | Koningsdag | Public | lun 27 abr | mar 27 abr |
| 6 | Liberation Day | Bevrijdingsdag | Public sector (every 5 years fully public; in 2025/2030/2035 it's a full holiday) | mar 5 may (5-yr) | mié 5 may (not 5-yr) |
| 7 | Ascension Day | Hemelvaartsdag | Public | jue 14 may | jue 6 may |
| 8 | Whit Sunday | Eerste Pinksterdag | Public | dom 24 may | dom 16 may |
| 9 | Whit Monday | Tweede Pinksterdag | Public | lun 25 may | lun 17 may |
| 10 | Christmas Day | Eerste Kerstdag | Public | vie 25 dic | sáb 25 dic |
| 11 | Boxing Day | Tweede Kerstdag | Public | sáb 26 dic | dom 26 dic |

### 5.2 Non-public but culturally important (NL)

| Event | Date rule | 2026 | 2027 | For La Vaquita |
|---|---|---|---|---|
| **Sinterklaasavond (Pakjesavond)** | **5 December (not a public holiday but bigger than Christmas for many)** | sáb 5 dic | dom 5 dic | **MEDIUM** — the iconic NL Speculaas/Pepernoten/Kruidnoten are baked items La Vaquita could offer in December (cultural connection to the "Holandesa" brand) |
| **Sinterklaas arrival (Intocht)** | Mid-November (3rd Saturday since 2019) | sáb 14 nov 2026 | sáb 13 nov 2027 | LOW |
| **Moederdag (Mother's Day NL)** | 2nd Sunday of May | dom 10 may 2026 | dom 9 may 2027 | LOW (PY is 15 May, dominant for Saskia) |
| **Vaderdag (Father's Day NL)** | 3rd Sunday of June | dom 21 jun 2026 | dom 20 jun 2027 | LOW |
| **Valentijnsdag (Valentine's Day NL)** | 14 February | sáb 14 feb 2026 | dom 14 feb 2027 | LOW |
| **Prinsjesdag (Budget Day)** | 3rd Tuesday of September | mar 15 sep 2026 | mar 21 sep 2027 | LOW |
| **Dodenherdenking (Remembrance)** | 4 May (eve of Bevrijdingsdag) | lun 4 may 2026 | mar 4 may 2027 | LOW |
| **Keti Koti (Emancipation Day)** | 1 July | mié 1 jul 2026 | jue 1 jul 2027 | LOW |
| **Carneval (Limburg/Brabant)** | Sun-Sun before Ash Wednesday | 15-22 feb 2026 (Easter Apr 5) | 7-14 feb 2027 (Easter Mar 28) | LOW (southern NL only, not relevant for PY) |

### 5.3 NL School holidays (vakanties) — 3 regions, official for 2026-2030

| Vakantie | Region Noord 2026-27 | Region Midden 2026-27 | Region Zuid 2026-27 |
|---|---|---|---|
| Herfstvakantie (autumn) | 10-18 okt 2026 | 17-25 okt 2026 | 17-25 okt 2026 |
| Kerstvakantie (Christmas) | 19 dec 2026 - 3 jan 2027 | (same) | (same) |
| Voorjaarsvakantie (spring) | 20-28 feb 2027 | 20-28 feb 2027 | 13-21 feb 2027 |
| Meivakantie (May) | 24 apr - 2 mei 2027 | (same) | (same) |
| Zomervakantie (summer) | 10 jul - 22 aug 2027 | 17 jul - 29 aug 2027 | 24 jul - 5 sep 2027 |

**For La Vaquita**: NL school holidays are **not relevant** (no NL clients); informational only. The brand is symbolic, not commercially tied to NL school calendar.

### 5.4 The "Vaquita Holandesa" cultural connection (what to leverage)

La Vaquita's Dutch heritage is in the **brand name** ("La Vaca Holandesa" = the Dutch cow, an iconic image of NL dairy farming). The actual connection to NL culture for the bakery's catalog is **narrow and seasonal**:

- **Sinterklaas season (late Nov - 6 Dec)**: the "speculaas / kruidnoten / pepernoten" cluster is iconic NL Christmas. La Vaquita could offer a "Holandesa Christmas Box" with speculaas + kruidnoten. Demand is mostly Dutch-heritage community in PY + nostalgic Dutch-Paraguayan families. **MEDIUM impact** (not high-volume but high-margin specialty).
- **Koningsdag (27 April)**: NL King's birthday. PY has a tiny NL-heritage community (~5,000 NL-born + mixed families in Asunción, per the Dutch-Paraguayan Society). **LOW impact** (informational only).
- **Bevrijdingsdag (5 May)**: NL liberation. **LOW impact** (not a PY thing).

**Conclusion**: the Dutch heritage angle is **brand/storytelling**, not commercial demand. The SeasonalEvent catalog should include Sinterklaas with a "heritage" tag but **not** make it drive production. The 13 PY legal holidays + 10+ PY commercial days + the Catholic movable feasts are the real drivers.

---

## 6. Model schema proposal (SASKIA-216)

The current schema has **no SeasonalEvent model**. The seed (SASKIA-213) inserts business hours / branding / location, but the **event-driven demand** layer is missing. Here's the proposed schema:

### 6.1 The model (single table, polymorphic-ish for multi-tenant relevance)

```python
class SeasonalEvent(Base):
    """A date-anchored demand driver for production planning.

    SASKIA-216 (2026-10-12) — informed by the 2026-10-08 onboarding
    questionnaire §16.1 (Semana Santa = si), §16.5 (Menú estacional
    verano/invierno = si), §16.6 (Aviso 30 días antes = si, already
    wired as `seasonal.notif_lead_days` setting).

    Stores one row per (event, year). Each row carries a `relevance_tag`
    so each tenant instance can show only the events that matter to its
    market (PY bakery, NL café, pizzeria, etc.). The 30-day lead time
    is applied at READ time, not stored, so a single setting can be
    changed without rewriting the events.
    """

    __tablename__ = "seasonal_event"

    id = Column(Integer, primary_key=True)
    # Identity
    slug = Column(String(80), nullable=False, index=True)  # e.g. "semana_santa", "reyes"
    name_es = Column(String(120), nullable=False)
    name_nl = Column(String(120), nullable=True)  # for NL heritage events
    name_en = Column(String(120), nullable=True)  # optional, for exports
    description = Column(Text, nullable=True)
    # Date
    event_date = Column(Date, nullable=False, index=True)  # the actual date
    # OR for multi-day events: end_date (inclusive, nullable)
    end_date = Column(Date, nullable=True)
    # Classification
    country = Column(String(2), nullable=False, default="PY", index=True)  # ISO-3166-1 alpha-2
    category = Column(
        String(20), nullable=False, index=True
    )  # "legal" / "commercial" / "religious" / "school" / "folk" / "sectoral" / "heritage"
    # Demand impact (0.0 - 1.0, used for production scaling)
    impact_score = Column(
        Float, nullable=False, default=0.5
    )  # 1.0 = critical (Semana Santa for panadería), 0.1 = informational
    impact_tag = Column(
        String(20), nullable=False, default="medium"
    )  # "critical" / "high" / "medium" / "low" / "info"
    # Multi-tenant filter
    relevance_tags = Column(
        String(200), nullable=False, default=""
    )  # CSV: "panaderia,cafeteria,pizzeria" — empty = all
    # The lead-time for advance notification is a setting, not a column
    is_annual = Column(Boolean, nullable=False, default=False)  # True for fixed-date holidays
    # Computus anchor (for movable feasts): ISO 8601 recurrence rule or weekday-of-month
    # e.g. Easter Sunday = computus(year); "3rd Sunday of June" = nth-weekday
    recurrence = Column(
        String(80), nullable=True
    )  # e.g. "easter", "easter-2", "third-sunday-june", "fixed", "movable-by-decree"
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```

### 6.2 Why this shape (decisions baked in)

- **`slug` + `(country, event_date)`** unique key — the same event ("Semana Santa") can be stored as 3 rows: 2026, 2027, 2028. The slug identifies the event across years; the date identifies the specific instance.
- **`country`** — explicit because the multi-tenant architecture (OOB) means the next client could be in NL, AR, or elsewhere. Today we seed PY + a few NL heritage rows; tomorrow we can add a pack for NL clients without schema changes.
- **`category` + `impact_score` + `impact_tag`** — three axes for the same idea, because:
  - `category` ("legal" vs "commercial") is for **filtering** (don't show "Sinterklaas" to a panadería operator unless they want it)
  - `impact_score` (0.0-1.0) is for **math** (production scaling: multiply forecast by 1.5 if event is 0.5)
  - `impact_tag` is for **UI** (red / yellow / green dot in the calendar)
- **`relevance_tags`** (CSV) — the multi-tenant knob. Empty = show to all clients. "panaderia" = show to bakeries. "cafeteria" = show to cafés. This lets the same row be "visible" to multiple verticals with different impact.
- **`is_annual` + `recurrence`** — for the seed. Annual fixed dates (Año Nuevo, Navidad) have `is_annual=True, recurrence="fixed"`. Easter-dependent (Semana Santa) have `is_annual=False, recurrence="easter-3"`. Movable-by-decree (Héroes, Boquerón) have `is_annual=False, recurrence="movable-by-decree"`. The seed inserts the **actual date for 2026-2028**; from 2029+ the model needs a runtime computus (out of scope for this ticket — a separate job can roll forward annually).
- **`name_es` + `name_nl` + `name_en`** — multilingual labels so the Sazon UI can show the right one based on the tenant's locale.
- **No `tenant_id` FK** — SeasonalEvent is **shared across tenants** (per OOB multi-tenant direction). The `relevance_tags` filter is what makes the same row visible to one tenant and invisible to another. This keeps the seed catalog small (~50-100 rows per country per year) and avoids per-tenant duplication.

### 6.3 What does NOT go in this table

- **Daily sales / production data** — that's `Sale`, `ProductionPlan`, `ProductionCompletion`. SeasonalEvent only stores the **calendar**, not the demand outcome.
- **Per-tenant event overrides** — if a tenant wants to mark "Black Friday" as a no-op, that's a `TenantSeasonalEventOverride` table (out of scope for SASKIA-216; defer to SASKIA-218).
- **Recurring event definitions** (RRULE) — the seed inserts actual dates; runtime expansion is a separate cron job (SASKIA-219).

---

## 7. Seed catalog proposal (the rows to insert in SASKIA-216)

### 7.1 The ~50 rows for La Vaquita (PY + a few NL heritage)

The seed would insert **one row per event per year** (2026, 2027, 2028) for these:

**Tier 1 — CRITICAL (impact_score=1.0, impact_tag="critical")**
1. Semana Santa (Jueves Santo) — rec=easter-3, 2026/27/28
2. Semana Santa (Viernes Santo) — rec=easter-2
3. Pascua (Easter Sunday) — rec=easter, also Rosca de Pascua
4. Día de la Madre PY — fixed 15 May
5. Navidad — fixed 25 December
6. Año Nuevo — fixed 1 January
7. Reyes / Epifanía — fixed 6 January (Rosca de Reyes)
8. San Juan Ára — fixed 24 June (chipá, mbejú — the iconic San Juan foods)
9. San Lorenzo patron (district) — fixed 10 August (Saskia's local demand spike)
10. Asunción patron (Fundación) — fixed 15 August

**Tier 2 — HIGH (impact_score=0.8, impact_tag="high")**
11. Día del Niño PY — fixed 16 August
12. Día del Amigo PY — fixed 30 July
13. Independencia Nacional (eve + day) — fixed 14 + 15 May
14. Inicio de clases PY — per MEC resolución (the "snack season" opens)
15. Fin de clases PY — last business day of November (snack season closes)
16. Nochebuena — fixed 24 December
17. Virgen de Caacupé — fixed 8 December (national patron)

**Tier 3 — MEDIUM (impact_score=0.5, impact_tag="medium")**
18. Carnaval Encarnaceno — 5 Saturdays Jan-mid-Feb (Encarnación only)
19. Día del Padre PY — 3rd Sunday of June
20. Día del Maestro — fixed 30 April
21. Día de la Mujer — fixed 8 March
22. Día de los Héroes de la Patria — fixed 1 March (movable)
23. Día de los Trabajadores — fixed 1 May
24. Paz del Chaco — fixed 12 June (movable)
25. Jura de la Constitución — fixed 20 June (movable, new 2025)
26. Batalla de Boquerón — fixed 29 September (movable)
27. Vacaciones de invierno PY (start + end) — per MEC
28. Black Friday PY — last Friday of November
29. CyberDay PY — first Monday-Wednesday of November (when announced)
30. Cuaresma (Lent) — Ash Wednesday, rec=easter-46
31. Corpus Christi — rec=easter+60
32. Sinterklaas (NL heritage) — fixed 5 December, country=NL, relevance=heritage

**Tier 4 — LOW (impact_score=0.3, impact_tag="low")**
33. Día del Panadero (informal) — mid-March
34. Día de los Almaceneros — fixed 8 August
35. Día de la Música PY — fixed 22 November
36. Día de los Pueblos Originarios — fixed 12 October
37. Primavera + Juventud — fixed 21 September
38. Día Nacional del Tereré — last Saturday of February
39. Singles Day (11.11) — fixed 11 November
40. Halloween — fixed 31 October
41. Día de San Valentín — fixed 14 February

**Tier 5 — INFO (impact_score=0.1, impact_tag="info", for the heritage angle)**
42. Koningsdag NL — fixed 27 April, country=NL, relevance=heritage
43. Bevrijdingsdag NL — fixed 5 May, country=NL, relevance=heritage
44. King's Birthday (NL patron saint equivalent for Saskia's brand story) — informational

That's **44 distinct event types × 3 years = 132 rows** in the seed catalog.

### 7.2 What the seeder writes (per Sazon convention)

The seeder (`app/rms/seed/sazon.py::_seed_seasonal_events`) would insert these 132 rows. **Idempotent** like the other seeders (skip if `slug + year + country` exists). **No backfill needed** for fresh installs; for existing DBs, running the seeder inserts the missing rows.

---

## 8. Migration + sequencing plan

### 8.1 Migration 119 (proposed for SASKIA-216)

- Add `seasonal_event` table per §6.1 schema
- Add `id`, `slug`, `name_es`, `name_nl`, `name_en`, `description`, `event_date`, `end_date`, `country`, `category`, `impact_score`, `impact_tag`, `relevance_tags`, `is_annual`, `recurrence`, `created_at`, `updated_at` columns
- Add unique constraint on `(country, slug, event_date)` (or `(country, slug, year)` if I add a `year` column instead of using `event_date`)
- Bump `CURRENT_SCHEMA_VERSION` 118 → 119

### 8.2 Seeder changes

- Add `_seed_seasonal_events(ctx)` helper to `sazon.py` that inserts the 132 rows from §7.1
- Call it after `_seed_settingskv_branding` in the main `seed_sazon()` flow
- The seeder is **idempotent**: insert only if `(country, slug, event_date)` is missing

### 8.3 UI changes (out of scope for SASKIA-216)

- Add a `/admin/seasonal-calendar` page that lists upcoming events (filtered by `event_date >= today - 30 days` and `relevance_tags` matching the tenant's vertical)
- Respect `seasonal.notif_lead_days` setting (default 30, SASKIA-215): events more than 30 days out show in the calendar; events less than 30 days out show a "URGENT" badge
- The first release of this UI is a **read-only** calendar; editing events is a future ticket

### 8.4 Risks

- **Low schema risk** — adding one new table doesn't affect existing models.
- **Medium seeder risk** — the 132 rows are mostly data, not logic; if a date is wrong, fixing it is a 1-row update.
- **High cognitive risk** — the catalog has 132 rows. Operators (Saskia) will see a lot. The UI must filter (per-tenant relevance_tags) and group (by month, by impact) aggressively.
- **External dependency risk** — some dates (CyberDay, Carnaval) are announced yearly by organizers; the seeder must be re-run annually. Add a `scripts/refresh_seasonal_events.py` cron-friendly script.

---

## 9. Sources (all web-cited, retrieved 2026-10-12)

### PY legal
- `https://www.bacn.gov.py/leyes-paraguayas/12908/ley-n-7544-2025-que-determina-los-feriados-nacionales-de-la-rep-blica-del-paraguay...` — Ley 7544/2025 (official text, BACN)
- `https://latamref.dev/py/public-holidays` — verified 2026-07-30 against BACN
- `https://bestparaguay.com/es/vivir/feriados-en-paraguay/` — read 2026-10-07
- `https://www.calendarioparaguay.com/calendario-2027.html` — verified
- `https://pytagua.com/en/paraguay-public-holidays/` — English summary

### PY commercial
- `https://expertosnegociosonline.com/blog/calendario-comercial-ecommerce-paraguay/` — 2027 calendario comercial
- `https://tiendli.com/blog/calendario-fechas-comerciales-2026` — AR/UY/PY 2026 commercial calendar
- `https://guia.fenicio.help/bienvenida-clientes/eventos-y-campanas/calendario-comercial` — Fenicio PY 2026 (PDF)
- `https://ahendu.com.py/economia/cyberday-paraguay-2026-2-al-4-de-noviembre` — CyberDay 2026 dates
- `https://www.abc.com.py/edicion-impresa/suplementos/comercial/dia-del-panadero-2025/...` — Día del Panadero 2025 (industry tradition)
- `https://www.lanacion.com.py/politica/2026/09/01/sancionan-proyectos-que-establecen-los-dias-de-los-almaceneros...` — Día de los Almaceneros 2026

### PY culture / patronales
- `https://asuncioncity.com/es/fechas/` — Asunción dates
- `https://asuncioncity.com/en/agenda/` — festivals and events calendar (36 patronales listed)
- `https://informacionpublica.paraguay.gov.py/public/1491818-2FESTIVIDADESpdf-2.FESTIVIDADES.pdf` — official PY festividades
- `https://www.abc.com.py/nacionales/2026/08/10/san-lorenzo-celebra-su-aniversario-entre-historia-fe-y-tradicion/` — San Lorenzo 251st anniversary
- `https://www.sanlo.gov.py/index.php/contacto/mi-ciudad-mi-pueblo` — San Lorenzo city history
- `https://www.abc.com.py/nacionales/2023/06/22/los-origenes-de-la-fiesta-de-san-juan-en-paraguay/` — San Juan history
- `https://www.bbc.com/mundo/cultura_sociedad/2010/06/100625_paraguay_fiesta_san_juan_jrg` — BBC San Juan Ára
- `https://www.ultimahora.com/san-juan-ara-tradicion-que-persiste-n805739` — San Juan Ára persistence
- `https://www.portalguarani.com/detalles_museos_otras_obras.php?PqwoiflUYTeslk=MjQyNA%3D%3D` — Santos Patronos PY

### PY school calendar
- `https://www.latribuna.com.py/nacionales/2026/06/23/vacaciones-de-invierno-esto-es-lo-que-debe-saber/` — vacaciones de invierno 2026
- `https://ahendu.com.py/sociedad/calendario-escolar-2027-paraguay` — 2027 calendar not yet published
- `https://www.paraguaytv.gov.py/2025/12/19/mec-aprueba-calendario-educativo-2026-clases-inician-el-23-de-febrero-y-cierran-el-30-de-noviembre/` — MEC Res. 2.065
- `https://ahendu.com.py/sociedad/calendario-escolar-2026-vacaciones` — 2026 calendar

### NL legal
- `https://www.rijksoverheid.nl/vraag-en-antwoord/arbeidsovereenkomst-en-cao/officiele-feestdagen` — official NL feestdagen 2026-2027
- `https://www.datkanikzelf.nl/handig/feestdagen/` — 2026-2027 feestdagen
- `https://www.timeanddate.com/holidays/netherlands` — NL holidays + observances
- `https://www.nlcompass.com/guides/dutch-public-holidays-netherlands` — 2026 dates
- `https://www.amsterdamtips.com/netherlands-public-holidays` — 2026/2027/2028 official

### NL school holidays
- `https://www.rijksoverheid.nl/themas/onderwijs/schoolvakanties/overzicht-schoolvakanties-per-schooljaar/overzicht-schoolvakanties-2026-2027` — official 2026-2027
- `https://zoek.officielebekendmakingen.nl/stcrt-2024-19237.html` — Regeling 2025-2030 (Staatscourant)

### NL heritage (Sinterklaas, etc.)
- `https://npokennis.nl/longread/7910/waarom-vieren-we-sinterklaas?andereTalen=1` — Sinterklaas history
- `https://www.stnicholascenter.org/around-the-world/customs/netherlands` — Sinterklaas NL
- `https://www.dachist.org/en/netherlands/public-holidays/saint-nicholas-eve.html` — Pakjesavond
- `https://www.beleven.org/feest/sinterklaas` — Sinterklaas 2026

### Easter computus
- `https://www.usccb.org/resources/2027cal.pdf` — USCCB 2027 liturgical calendar
- `https://calcgallery.com/date-time/easter-date-calculator/` — Easter 2026-2030
- `https://www.catholicchurchtimes.com/calendar/easter/2027` — 2027 with all movable feasts
- `https://countfolk.com/western-orthodox-easter-date-calculator/` — computus algorithm

### PY Carnaval
- `https://visitparaguay.travel/events/carnaval-encarnaceno-2026-edicion-100` — Edición 100
- `https://www.cuandopasa.com/index.php?v=v118172c` — 2027 dates
- `https://carnivalvibez.com/encarnacion-carnival/` — 2027 Saturday nights
- `https://www.carnavalencarnaceno.com.py/` — official site

---

## 10. What's next (recommended ticket sequencing)

1. **SASKIA-216 (this ticket)**: implement the SeasonalEvent model + migration 119 + seeder for the 132 rows. **2-3 days work.**
2. **SASKIA-217 (followup)**: add the `/admin/seasonal-calendar` UI page (read-only). Respect `seasonal.notif_lead_days` setting. **2-3 days.**
3. **SASKIA-218 (future)**: add `TenantSeasonalEventOverride` table for per-tenant event visibility/impact customization. **1 day.**
4. **SASKIA-219 (future)**: add `scripts/refresh_seasonal_events.py` cron that rolls forward the Easter-dependent and decree-dependent events annually. **1 day.**
5. **SASKIA-214 (already drafted)**: refactor `seed_sazon` to call `onboard_tenant()` with per-instance params. The SeasonalEvent catalog becomes a parameter of `onboard_tenant()`. **4-6h.**

The **highest priority** is SASKIA-216 because it's the **blocker** for "load all the things" (the OOB directive). Until the model exists, the website cannot render the seasonal calendar.
