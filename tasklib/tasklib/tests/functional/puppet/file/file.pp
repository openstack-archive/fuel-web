file {"tasklibtest":
  path    => "/tmp/tasklibtest",
  ensure  => present,
  mode    => 0640,
  content => "I'm a file created created by tasklib test",
}