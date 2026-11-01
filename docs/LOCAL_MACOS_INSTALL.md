# Installer sa compilation macOS sur ce Mac

Ce parcours développeur compile des sources commitées et prépare une installation
personnelle avec sauvegarde. Il n'est pas embarqué dans l'application et ne modifie
pas le parcours des téléchargements publics. Gatekeeper reste actif.

## Préparer

- macOS, Git, Python 3.12 et les dépendances de `requirements-build.txt` installées
  dans l'environnement Python choisi (voir [DEVELOPMENT.md](DEVELOPMENT.md)).
- Une copie examinée de `ArN-LaB/homebrew-tap`, contenant
  `developer-tools/macos-local-installer`, version **0.1.1**. La référence prévue
  `local-installer-v0.1.1` attend la validation humaine et n'est pas encore publiée.
  Pendant la revue, utiliser la copie locale du composant. La référence partagée doit être publiée avant cette intégration.
- Sources SpoolScribe propres : préserver puis commiter ses changements avant le build.

```sh
export ARNLAB_PYTHON="$PWD/.venv/bin/python"
# Seulement si homebrew-tap n'est pas au chemin habituel ~/Documents/GitHub :
export ARNLAB_INSTALLER_ROOT="/chemin/homebrew-tap/developer-tools/macos-local-installer"
./install-local.command --dry-run
./install-local.command --build-only
./install-local.command --build --simulate
./install-local.command
```

Le double-clic sur `install-local.command` ouvre le parcours interactif avec `python3`.
Choisir `ARNLAB_PYTHON` dans Terminal si cet interpréteur n'a pas les dépendances.
Le SHA-256 et la version du composant sont épinglés dans `.macos-local-install.json`.
Aucun script distant n'est téléchargé ou exécuté automatiquement.

La compilation utilise un export Git dans un dossier privé distinct ; les anciens
`build/`, `dist/`, données personnelles, préférences, catalogue et profils Orca du Mac
ne sont pas écrasés. La commande PyInstaller et le spec multiplateforme sont inchangés.
La source du bundle est `dist/SpoolScribe.app` dans cet export, avec l'identifiant
`com.github.arn-lab.spoolscribe`.

## Installer ou revenir en arrière

La compilation affiche un chemin de bundle et un reçu UUID privé. On peut réutiliser
ce même build sans recompiler :

```sh
./install-local.command --app /chemin/SpoolScribe.app --receipt UUID_DU_RECU
./install-local.command --rollback UUID_DE_TRANSACTION
./install-local.command --list-backups
```

Quitter normalement l'application cible avant installation ou restauration ; le moteur
contrôle son activité sans arrêter de processus. Une cible gérée par Homebrew est
refusée. L'installation exige la saisie `INSTALLER`. Si une quarantaine est détectée, son
retrait sur la **copie préparée seulement** exige une seconde saisie `RETIRER`.
Refuser annule l'installation et préserve les fichiers existants. Une signature
invalide, un identifiant inattendu ou un fichier différent du reçu entraîne un refus.
Un ZIP GitHub ou son fichier SHA-256 ne remplace pas un reçu local : reconstruire
depuis les sources pour ce parcours. Aucune signature valide n'est remplacée.

Une mise à jour garde l'ancienne application dans
`/Applications/.arnlab-local-installer/UUID/previous.app`. Le retour arrière exige
`RESTAURER` et refuse les copies modifiées depuis leur installation. Les sauvegardes
et journaux sont conservés ; `--list-backups` indique leurs tailles et états sans
les supprimer. Aucune purge automatique : les examiner avant un nettoyage manuel.
Pas d'élévation de privilèges ni de lancement automatique de SpoolScribe.

Voir le [contrat et les limites du composant commun](https://github.com/ArN-LaB/homebrew-tap/tree/main/developer-tools/macos-local-installer).
Le guide sera accessible sur `main` après l'intégration du composant ; le manifeste
reste épinglé sur sa version et son SHA-256, jamais sur une branche mouvante.
La signature ad hoc d'un build personnel ne vaut pas notarisation ; le lancement
réel et les politiques d'administration de ce Mac restent à contrôler après validation.
