# Projectivy-FR

Générateur automatique de wallpapers 4K français pour Projectivy Launcher + Overflight.

## Mise en route
1. Créez un dépôt GitHub public et copiez-y ce dossier.
2. Obtenez un jeton **TMDB API Read Access Token**.
3. GitHub > Settings > Secrets and variables > Actions > New repository secret : `TMDB_API_TOKEN`.
4. Actions > « Mise à jour des wallpapers » > Run workflow.
5. Vérifiez que `wallpapers.json` et le dossier `wallpapers/` ont été générés.
6. Dans Overflight, utilisez comme source : `https://raw.githubusercontent.com/VOTRE_COMPTE/VOTRE_DEPOT/main/wallpapers.json`.
7. Dans Projectivy : Paramètres > Apparence > Fond d'écran > Overflight.

## Mise en page adaptée à votre écran
- 3840×2160.
- Informations concentrées en haut à gauche (environ Y 110–850).
- Bande centrale Y 900–1650 réservée au menu d'applications Projectivy.
- Synopsis limité à 3 grandes lignes.
- Données en `fr-FR`, région `FR`.
- Attribution JustWatch affichée pour les disponibilités de streaming.

## Réglages
Modifiez `config.json` pour le nombre de wallpapers, la période, les plateformes et les dimensions.
