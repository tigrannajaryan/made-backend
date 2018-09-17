# How many days of price calculation to perform at once
PRICE_BLOCK_SIZE = 14

# For a day which is not available for booking (because it is either fully
# occupied, or is not available for booking at all, we will consider demand
# value equal to 1 (demain is 0..1, 1 is completely booked)

COMPLETELY_BOOKED_DEMAND = 1
UNAVAILABLE_DEMAND = 1
