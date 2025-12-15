"""Resource Bridge Tool - allows clients to read resources via the Tools interface."""

from base import ChameleonTool
from runtime import get_resource, ResourceNotFoundError
from sqlmodel import select
from models import ResourceRegistry

class ReadResourceTool(ChameleonTool):
    def run(self, arguments):
        '''
        Read a resource by URI from the ResourceRegistry.
        
        This tool enables clients that only support Tools (not Resources)
        to fetch resource data manually.
        '''
        uri = arguments.get('uri')
        
        if not uri:
            return "Error: 'uri' parameter is required"
        
        # Get persona from context, default to 'default'
        persona = self.context.get('persona', 'default')
        
        try:
            # Call get_resource to fetch the resource
            result = get_resource(uri, persona, self.db_session)
            return result
        except ResourceNotFoundError as e:
            # Query ResourceRegistry for available URIs to help self-correction
            statement = select(ResourceRegistry).where(
                ResourceRegistry.target_persona == persona
            )
            available_resources = self.db_session.exec(statement).all()
            
            if available_resources:
                available_uris = [r.uri_schema for r in available_resources]
                uris_list = '\n  - '.join(available_uris)
                return f"Resource not found: {uri}\n\nAvailable resources are:\n  - {uris_list}"
            else:
                return f"Resource not found: {uri}\n\nNo resources available for persona '{persona}'"
