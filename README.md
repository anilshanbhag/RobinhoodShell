# Robinhood Shell

Robinhood Shell is a command line shell for trading stocks using Robinhood.

![Robinhood Shell](https://i.imgur.com/XjrtYXB.png)

Commands Supported
------------------ 

* `l` : Lists your current portfolio
* `b <symbol> <quantity> <price>` : Submits a limit order to buy <quantity> stocks of <symbol> at <price>
* `s <symbol> <quantity> <price>` : Submits a limit order to sell <quantity> stocks of <symbol> at <price>
* `o` : Lists all open orders
* `c <id>` : Cancel an open order identified by <id> [<id> of a open order can be got from output of `o`]
* `bye` : Exit the shell  

Setup
-----

Download Robinhood Shell by downloading the zip file ([link](https://github.com/anilshanbhag/RobinhoodShell/archive/master.zip)) OR by using git 
```
git clone git@github.com:anilshanbhag/RobinhoodShell.git
```

Install the dependencies
```
sudo pip install -r requirements.txt
```

Create and save your username/password in the config file
```
cp config.py.sample config.py
# Edit config.py - replace username/password with your real username/password
```

You are good to go. Start the shell by
```
chmod +x shell.py
./shell.py
```

Credits
-------
The shell builds on [Robinhood Python API wrapper](https://github.com/Jamonek/Robinhood) by Jamonek

Disclaimer
---------
Robinhood Shell is not associated with the Robinhood app or endorsed by it. 
