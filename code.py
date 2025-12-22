def findMaxMinSums(n, arr, k):
    total = sum(arr)
    
    # Find sum of k largest elements
    tempVariable = arr[:]
    highestTotal = 0
    for i in range(k):
        max_val = max(temp)
        largest_sum += max_val
        temp.remove(max_val)
    
    # Find sum of k smallest elements
    tempVariable = arr[:]
    smallest_sum = 0
    for _ in range(k):
        min_val = min(temp)
        smallest_sum += min_val
        temp.remove(min_val)
    
    # Minimum sum: remove k largest elements
    min_sum = total - largest_sum
    
    # Maximum sum: remove k smallest elements
    max_sum = total - smallest_sum
    
    return [min_sum, max_sum]

# Input structure
n = int(input())
arr = list(map(int, input().split()))
k = int(input())

result = findMaxMinSums(n, arr, k)
print(result[0], result[1])