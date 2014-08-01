
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
                'name': 'move',
                'from': 'from_path',
                'to': 'to_path',
            },
            {
                'name': 'symlink',
                'from': 'from_path',
                'to': 'to_path',
            }
        ])

    def test_constructor(self):
        self.assertEqual(len(self.manager._actions), 3)
        self.assertEqual(len(self.manager._history), 0)

        self.assertTrue(
            isinstance(self.manager._actions[0], actions.Copy))
        self.assertTrue(
            isinstance(self.manager._actions[1], actions.Move))
        self.assertTrue(
            isinstance(self.manager._actions[2], actions.Symlink))

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

    def test_complex_undo(self):
        self.action = actions.Copy(**{
            'from': 'path/to/src',
            'to': 'path/to/dst',
            'undo': [
                {
                    'name': 'move',
                    'from': 'one',
                    'to': 'two',
                },
                {
                    'name': 'copy',
                    'from': 'one',
                    'to': 'two',
                }
            ]
        })
        self.assertTrue(
            isinstance(self.action.undo.__self__, actions.ActionManager))
        self.assertEqual(len(self.action.undo.im_self._actions), 2)

        mocks = [mock.Mock(), mock.Mock()]
        self.action.undo.im_self._actions = mocks
        self.action.undo()

        for action in mocks:
            self.called_once(action.do)


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


class TestSymlinkAction(BaseTestCase):

    def setUp(self):
        self.action = actions.Symlink(**{
            'from': 'path/to/src',
            'to': 'path/to/dst',
        })

    @mock.patch('fuel_upgrade.actions.symlink')
    def test_do(self, symlink):
        self.action.do()
        symlink.assert_called_once_with('path/to/src', 'path/to/dst', True)

    @mock.patch('fuel_upgrade.actions.remove')
    def test_undo(self, remove):
        self.action.undo()
        remove.assert_called_once_with('path/to/dst')
