# Per-ingredient visual specs — tells the AI the SPECIFIC container, color,
# and shape for each ingredient so the result is recognizable at 32x32 px.

INGREDIENT_VISUALS = {
    # HARINAS Y BASES
    "harina_de_centeno": "an open 1kg kraft paper bag of rye flour with flour spilling slightly, the flour visible as a tan-brown powder, simple and bold",
    "harina_de_reposteria": "an open 1kg kraft paper bag of fine cake/pastry flour (white), small mound of white flour visible",
    "harina_de_trigo": "an open 1kg kraft paper bag of bread flour (white), with a small handful of wheat grains next to it",
    "harina_patentada": "a 1kg kraft paper bag of high-extraction wheat flour, slightly off-white",
    "maicena": "a 1kg kraft paper bag labeled MAICENA with cornstarch visible (fine white powder)",
    "pan_rallado": "a clear plastic bag of pale golden breadcrumbs, simple and bold",
    "masa_de_hojaldre": "a folded square of raw puff pastry dough, pale yellow, with visible lamination layers on the side, on parchment paper",
    # ENDULZANTES
    "azucar": "a 1kg clear plastic bag of white granulated sugar, the crystals visible",
    "azucar_glas": "a 1kg clear plastic bag of fine white powdered sugar with a small dust cloud visible",
    "azucar_morena": "a 1kg clear plastic bag of brown sugar with the dark crystals visible, simple and recognizable",
    "melaza": "a small glass jar of dark brown-black molasses syrup, thick and viscous",
    "miel": "a small glass jar of amber honey, with a honey dipper dripping",
    # LACTEOS Y HUEVOS
    "crema_agria": "a small white ceramic bowl of thick white sour cream, simple",
    "crema_de_leche": "a 1L glass bottle of heavy cream with a white layer visible",
    "crema_pastelera": "a small saucepan of thick pale yellow pastry cream, spoonable",
    "huevos": "a small grey pulp-egg-carton with 6 brown farm eggs, simple and bold",
    "leche": "a 1L glass bottle of fresh white milk, simple and clear",
    "leche_condensada": "a 414g can of condensed milk, the blue-and-white can design with MILK letters",
    "manteca": "a wrapped block of yellow unsalted butter, ~250g, simple",
    "mascarpone": "a 250g tub of white mascarpone cheese, simple",
    "nata": "a small carton of fresh whipping cream, simple",
    "queso_crema": "a 250g block of cream cheese (Philadelphia-style), wrapped in foil, simple",
    "queso_crema_dulce": "a 250g block of sweet cream cheese, simple",
    "queso_para_untar": "a 250g tub of spreadable cheese, simple",
    # LEVADURAS Y GASIFICANTES
    "bicarbonato_de_sodio": "a small cardboard box of baking soda, white powder visible, simple",
    "levadura_fresca": "a small block of fresh yeast (~50g), beige crumbly texture, simple",
    "levadura_seca": "a small foil sachet of dry yeast (red/white design), simple",
    "polvo_de_hornear": "a small tin of baking powder, white powder visible, simple",
    # CACAO CAFE Y CHOCOLATE
    "cacao_en_polvo": "a 250g tin of unsweetened cocoa powder, the dark brown powder visible, simple",
    "cafe_instantaneo": "a 200g glass jar of instant coffee granules, dark brown, simple",
    "chocolate": "a 1kg bag of dark chocolate chips or callets, dark brown color, simple",
    # FRUTAS Y FRUTOS SECOS
    "frambuesas": "a small white bowl of fresh red raspberries, simple and recognizable",
    "fruta": "a small white bowl of mixed fresh fruit (sliced apple, orange, banana), simple",
    "nueces": "a small white bowl of shelled walnut halves, recognizable brain-like texture, simple",
    "pasas": "a small white bowl of dark wrinkled raisins, simple",
    "frutilla": "a small white bowl of fresh red strawberries with green tops, simple",
    "arandanos": "a small white bowl of fresh dark blue blueberries, simple",
    "frutas_confitadas": "a small white bowl of mixed candied fruit (red, green, yellow), simple",
    "lima": "a single whole fresh green lime, simple and bold",
    "limon": "a single whole fresh yellow lemon, simple and bold",
    # SALSAS Y LIQUIDOS
    "agua": "a clear glass jug of fresh water, simple and clean",
    "jugo_de_limon": "a small glass bottle of fresh lemon juice, pale yellow, simple",
    "jugo_de_remolacha": "a small glass bottle of deep red beet juice, simple",
    "vinagre": "a 500ml glass bottle of white vinegar, simple",
    "ketjap_manis": "a small glass jar of Indonesian sweet soy sauce, thick dark brown syrupy liquid, no label facing camera",
    "salsa_de_tomate": "a small glass jar of red tomato sauce/ketchup, simple",
    "mostaza": "a small glass jar of yellow mustard, simple",
    # VERDURAS Y LEGUMBRES
    "cebolla": "a single whole yellow onion with papery skin, simple and bold",
    "zanahoria": "a bunch of fresh orange carrots with green tops, simple",
    "garbanzo": "a small white bowl of dried chickpeas, simple and recognizable",
    "cebolla_morada": "a single whole red onion with purple papery skin, simple",
    "morron_rojo": "a single whole red bell pepper, simple and bold",
    # ESPECIAS Y CONDIMENTOS
    "laurel": "a small pile of dried bay leaves on a small wooden spoon, simple",
    "vainilla": "a small glass bottle of vanilla extract, dark amber liquid, simple",
    "ajo": "a single bulb of garlic with papery white skin, simple",
    "anis_estrellado": "a small pile of star anise pods, the star shape clearly visible",
    "canela": "a small bundle of cinnamon sticks tied with twine, recognizable rolled-bark shape",
    # CARNES
    "panceta_de_cerdo": "a thick slice of raw pork belly, raw pink meat with white fat layers, simple",
    "pechuga_de_pollo": "a whole raw chicken breast, pale pink, simple",
    "bola_de_lomo": "a whole raw beef tenderloin, deep red, simple",
    "carnaza_de_segunda": "a piece of raw beef chuck, deep red with marbling, simple",
    "falda_de_res": "a piece of raw beef skirt, deep red, simple",
    # PREPARADOS Y OTROS
    "estabilizante_para_nata": "a small foil sachet of cream stabilizer (gelatin), simple",
    "polvo_para_natillas": "a small yellow box of custard powder, simple",
    "masa_choux": "a ball of choux pastry dough, pale yellow, on parchment paper, simple",
    "gelatina": "a small box of powdered gelatin, simple",
    # ACEITES Y GRASAS
    "aceite": "a 1L glass bottle of neutral cooking oil, golden liquid, simple",
}
