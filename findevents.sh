grep "post(" *py | sed "s/ //g" | sed "s/.*post(//g" | sed "s/,.*//g" |sort|uniq

