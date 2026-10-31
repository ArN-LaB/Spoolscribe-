"""User-facing printer guidance; exporting a file is not writing a printer's tag."""
PROFILES = {
    'u1': {'label': 'Snapmaker U1 — firmware OpenSpool compatible', 'nfc': True,
           'help': 'OpenSpool : matière et couleur identifient le filament. Le profil du trancheur reste nécessaire pour imprimer. Vérifiez la version du firmware U1.',
           'fields': {'Type': 'Identification : requis', 'Couleur': 'Identification : requis', 'Marque': 'Identification : facultatif',
                      'Nozzle': 'Information stockée ; ne règle pas automatiquement la buse', 'Bed': 'Information stockée ; ne règle pas automatiquement le plateau',
                      'Diamètre': 'Trancheur ; non utilisé par le mapping U1 consulté', 'Densité': 'Calculs du trancheur ; non utilisé par le mapping U1 consulté',
                      'Masse': 'Inventaire ; non utilisé par le mapping U1 consulté'}},
    'u1_stock': {'label': 'Snapmaker U1 — firmware constructeur', 'nfc': False,
                 'help': 'L’export OpenSpool nécessite un firmware compatible. Aucun tag constructeur Snapmaker n’est généré.'},
    'bambu': {'label': 'Bambu Lab / AMS', 'nfc': False,
              'help': 'Fiche de référence pour Bambu Studio : matière, couleur et profil filament. SpoolScribe ne génère pas de tag RFID Bambu reconnu par l’AMS.',
              'fields': {'Type': 'À renseigner dans le profil/AMS', 'Couleur': 'À renseigner dans l’AMS',
                         'Nozzle': 'Réglage du profil Bambu Studio', 'Bed': 'Dépend du plateau sélectionné dans Bambu Studio',
                         'Diamètre': 'Compatibilité du filament avec l’imprimante', 'Densité': 'Calcul de masse du trancheur', 'Masse': 'Inventaire facultatif'}},
    'prusa': {'label': 'Prusa / PrusaSlicer', 'nfc': False,
              'help': 'Fiche de référence pour PrusaSlicer. OpenPrintTag utilise un autre format et des tags NFC-V : un NTAG215/216 OpenSpool ne le remplace pas. Encodeur OpenPrintTag non implémenté.',
              'fields': {'Type': 'Choix du profil filament', 'Couleur': 'Aperçu / identification', 'Nozzle': 'Réglage du profil PrusaSlicer',
                         'Bed': 'Réglage selon le plateau', 'Diamètre': 'Paramètre du trancheur', 'Densité': 'Calcul de masse du trancheur', 'Masse': 'Inventaire facultatif'}},
    'openspool': {'label': 'Autre lecteur OpenSpool', 'nfc': True,
                  'help': 'Export OpenSpool conservateur : tous les paramètres d’impression sont requis par SpoolScribe. Leur utilisation dépend du lecteur.'},
}
DEFAULT = 'u1'
