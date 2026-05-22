# MotionWake v1.0.0

Wekt het scherm automatisch op bij gedetecteerde beweging via webcam of Windows Hello sensor.

## Functies
- Bewegingsdetectie via alle cameras (inclusief IR / Windows Hello)
- Scherm blijft aan voor instelbare duur na detectie
- Systeemvak icoon met contextmenu
- Werkt voor alle gebruikers inclusief Kiosk user
- Draait als Windows Service (automatisch bij opstarten)
- Logging van alle acties

## Installatie
1. Download `MotionWake_Setup_vX.X.X.exe` uit de Releases
2. Voer de installer uit als Administrator
3. Kies volledige installatie of alleen software
4. De service start automatisch

## Gebruik
- Rechtsklik op het systeemvak icoon voor instellingen
- Pas gevoeligheid, camera en scherm-aan-duur aan
- Herstart de service na het opslaan van instellingen

## Windows Hello camera werkt niet?
- Ga naar Instellingen → selecteer de juiste camera index
- Windows Hello IR cameras staan vaak op index 1 of hoger
- De camera naam is zichtbaar in het instellingenmenu

## Commando's (als Administrator)
```
motionwake.exe --install    # Installeer Windows Service
motionwake.exe --uninstall  # Verwijder Windows Service
motionwake.exe --tray       # Start systeemvak app
```

## Versiebeheer
Zie [Releases](https://github.com/Edwardk360/motionwake/releases) voor alle versies.
