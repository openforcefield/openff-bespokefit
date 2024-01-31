from ..exceptions import InvalidGroupnameError as InvalidGroupnameError, InvalidPasswordError as InvalidPasswordError, InvalidRolenameError as InvalidRolenameError, InvalidUsernameError as InvalidUsernameError
from _typeshed import Incomplete
from enum import Enum
from pydantic import BaseModel, constr as constr
from typing import List, Optional, Union

class AuthTypeEnum(str, Enum):
    password: str

def is_valid_password(password: str) -> None: ...
def is_valid_username(username: str) -> None: ...
def is_valid_groupname(groupname: str) -> None: ...
def is_valid_rolename(rolename: str) -> None: ...

class PolicyStatement(BaseModel):
    Effect: str
    Action: Union[str, List[str]]
    Resource: Union[str, List[str]]

class PermissionsPolicy(BaseModel):
    class Config:
        extra: Incomplete
    Statement: List[PolicyStatement]

class RoleInfo(BaseModel):
    class Config:
        extra: Incomplete
    rolename: str
    permissions: PermissionsPolicy

class GroupInfo(BaseModel):
    class Config:
        extra: Incomplete
    id: Optional[int]
    groupname: str
    description: str

class UserInfo(BaseModel):
    class Config:
        validate_assignment: bool
        extra: Incomplete
    id: Optional[int]
    auth_type: AuthTypeEnum
    username: str
    role: str
    groups: List[str]
    enabled: bool
    fullname: None
    organization: None
    email: None
