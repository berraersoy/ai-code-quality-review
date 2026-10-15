def calculate_discount(price, is_member, has_coupon, is_holiday):
    if price <= 0:
        return 0

    if is_member:
        price *= 0.9

    if has_coupon:
        price -= 5

    if is_holiday:
        price *= 0.95

    if price < 0:
        return 0

    return price
