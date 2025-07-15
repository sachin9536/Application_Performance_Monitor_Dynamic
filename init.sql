-- Grant all privileges to testuser from any host
GRANT ALL PRIVILEGES ON *.* TO 'testuser'@'%' WITH GRANT OPTION;

-- Reload privilege tables
FLUSH PRIVILEGES;