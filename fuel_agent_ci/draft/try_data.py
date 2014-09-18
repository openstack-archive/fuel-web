import json
import jinja2


env = jinja2.Environment(loader=jinja2.FileSystemLoader('.'))
template = env.get_template('provision_data.json')
output = template.render(**{})
#     MASTER_IP='1.2.3.4',
#     IP='1.2.3.5',
#     MAC='00:00:00:00:00:00',
#     MASTER_HTTP_PORT='8888',
#     PROFILE='ubuntu_1204_x86_64'
# )


with open('provision_data2.json', 'wb') as f:
    f.write(output)
    f.flush()
