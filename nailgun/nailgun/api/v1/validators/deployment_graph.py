#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema.deployment_graph import \
    DEPLOYMENT_GRAPH_SCHEMA
from nailgun.api.v1.validators.json_schema.deployment_graph import \
    DEPLOYMENT_GRAPHS_SCHEMA


class DeploymentGraphValidator(BasicValidator):
    single_schema = DEPLOYMENT_GRAPH_SCHEMA
    collection_schema = DEPLOYMENT_GRAPHS_SCHEMA

    @classmethod
    def validate_update(cls, data, instance):
        parsed = super(DeploymentGraphValidator, cls).validate(data)
        cls.validate_schema(
            parsed,
            cls.single_schema
        )
        return parsed
