import argparse
from getpass import getpass
from ipaddress import IPv4Address

from miio import DeviceException

from BombillaLocal import Bulb, load_token, mensaje_error_conexion, save_profile


def main():
    parser = argparse.ArgumentParser(description="Control local de la bombilla Xiaomi")
    parser.add_argument("accion", choices=("estado", "encender", "apagar"), nargs="?", default="estado")
    parser.add_argument("--ip", type=IPv4Address)
    args = parser.parse_args()

    bulb = Bulb()
    if args.ip:
        bulb.ip = str(args.ip)
    try:
        saved = load_token()
        if not bulb.ip:
            parser.error("Indica --ip o guarda un perfil desde Luz.")
        token = saved or getpass("Token miIO de la bombilla (no se muestra): ").strip()
        if not saved:
            bulb = Bulb.identify(bulb.ip, token)
        status = bulb.control(token, "status" if args.accion == "estado" else "power", args.accion == "encender")
        if not saved:
            save_profile(bulb, token)
        print(status)
    except (DeviceException, OSError, ValueError) as error:
        detail = mensaje_error_conexion(error) or "Comprueba la conexión y el token de la bombilla."
        parser.exit(1, f"No se pudo completar la acción: {detail}\n")


if __name__ == "__main__":
    main()
