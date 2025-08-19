class Person:
    population = 0

    def __init__(self, name):
        self.name = name
        self.population += 1

    # @classmethod
    def get_population(self):
        return self.population,self.name

# 创建实例
p1 = Person("Alice")
p2 = Person("Bob")

print(Person.get_population(p2))  # 输出: 2
class MyClass:
    count = 0

    @classmethod
    def class_method(cls):
        print(f"类方法: cls -> {cls}, count = {cls.count}")

MyClass.class_method()  # cls = MyClass
obj = MyClass()
obj.class_method()      # cls 仍然是 MyClass
