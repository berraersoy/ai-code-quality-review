import math


def process_numbers(numbers):
    result = []

    for number in numbers:
        if number > 0:
            result.append(number * 2)

    return result


def divide(a, b):
    return a / b