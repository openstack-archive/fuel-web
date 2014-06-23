
import mock

from fuel_upgrade import actions
from fuel_upgrade.tests.base import BaseTestCase


class TestActionManager(BaseTestCase):

    def setUp(self):
        self.manager = actions.ActionManager([
            {
                'name': 'copy',
                'from': 'from_path',
                'to': 'to_path',
            },
            {
                'name': 'copy_from_update',
                'from': 'from_path',
                'to': 'to_path',
            },
            {
                'name': 'move',
                'from': 'from_path',
                'to': 'to_path',
            }
        ], base_path='bla-bla')

    def test_constructor(self):
        self.assertEqual(len(self.manager._actions), 3)
        self.assertEqual(len(self.manager._history), 0)

        self.assertTrue(
            isinstance(self.manager._actions[0], actions.Copy))
        self.assertTrue(
            isinstance(self.manager._actions[1], actions.CopyFromUpdate))
        self.assertTrue(
            isinstance(self.manager._actions[2], actions.Move))

    def test_do(self):
        self.assertEqual(len(self.manager._history), 0)

        for action in self.manager._actions:
            action.do = mock.Mock()

        self.manager.do()

        for action in self.manager._actions:
            self.called_once(action.do)

        self.assertEqual(len(self.manager._history), 3)

    def test_undo(self):
        self.manager._history = self.manager._actions
        for action in self.manager._history:
            action.undo = mock.Mock()

        self.manager.undo()

        for action in self.manager._history:
            self.called_once(action.undo)

        self.assertEqual(len(self.manager._history), 0)


class TestCopyAction(BaseTestCase):

    def setUp(self):
        self.action = actions.Copy(**{
            'from': 'path/to/src',
            'to': 'path/to/dst',
        })

    @mock.patch('fuel_upgrade.actions.copy')
    def test_do(self, copy):
        self.action.do()
        copy.assert_called_once_with('path/to/src', 'path/to/dst', True, True)

    @mock.patch('fuel_upgrade.actions.copy')
    def test_do_with_overwrite_false(self, copy):
        self.action._overwrite = False
        self.action.do()
        copy.assert_called_once_with('path/to/src', 'path/to/dst', False, True)

    @mock.patch('fuel_upgrade.actions.copy')
    def test_do_with_symlink_false(self, copy):
        self.action._symlinks = False
        self.action.do()
        copy.assert_called_once_with('path/to/src', 'path/to/dst', True, False)

    @mock.patch('fuel_upgrade.actions.remove')
    def test_undo(self, remove):
        self.action.undo()
        remove.assert_called_once_with('path/to/dst', ignore_errors=True)


class TestCopyFromUpdateAction(BaseTestCase):

    def setUp(self):
        self.action = actions.CopyFromUpdate(**{
            'from': 'path/to/src',
            'to': 'path/to/dst',
            'base_path': '/root',
        })

    def test_constructor(self):
        self.assertEqual(self.action.copy._from, '/root/path/to/src')

    def test_do(self):
        self.action.copy.do = mock.Mock()
        self.action.do()
        self.called_once(self.action.copy.do)

    def test_undo(self):
        self.action.copy.undo = mock.Mock()
        self.action.undo()
        self.called_once(self.action.copy.undo)


class TestMoveAction(BaseTestCase):

    def setUp(self):
        self.action = actions.Move(**{
            'from': 'path/to/src',
            'to': 'path/to/dst',
            'overwrite': False
        })

    @mock.patch('fuel_upgrade.actions.rename')
    def test_do(self, rename):
        self.action.do()
        rename.assert_called_once_with('path/to/src', 'path/to/dst', False)

    @mock.patch('fuel_upgrade.actions.rename')
    def test_undo(self, rename):
        self.action.undo()
        rename.assert_called_once_with('path/to/dst', 'path/to/src', False)
