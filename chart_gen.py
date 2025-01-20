r_vals = [10,12,15,18,22,27,33,39,47,56,68,75,82,91]
c_vals = [10,15,22,33,47,68]

res = []

for i in range(len(r_vals)):
    for j in range(i,len(r_vals)):
        for k in range(len(c_vals)):
            mod = float(r_vals[i]*r_vals[j]*c_vals[k])
            while mod >= 10.0:
                mod /= 10.0
            res.append((r_vals[i], r_vals[j], c_vals[k], mod))

res.sort(key=lambda x: x[3])
for r in res:
    print(f"{r[0]}x{r[1]}x{r[2]} {r[3]}")