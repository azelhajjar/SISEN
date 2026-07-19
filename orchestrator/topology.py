def build_interface_plan(config):
    devices = config["devices"]

    roles = []

    roles.append(("hmi", devices["hmi"]))
    roles.append(("scada_server", devices["scada_server"]))
    roles.append(("plc", devices["plc"]))
    roles.append(("rtu", devices["rtu"]))
    roles.append(("sensor", devices["sensors"]))

    plan = []
    interface_number = 1

    for role, count in roles:
        for index in range(1, count + 1):
            plan.append(
                {
                    "role": role,
                    "name": f"{role}-{index}",
                    "interface": f"wlan{interface_number}",
                }
            )
            interface_number += 1

    return plan
