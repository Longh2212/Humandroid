from Manager.Manager_Robot import RobotController
controller = RobotController()
controller.clear_buffer()
while True:
    id = input("nhap id ")
    angle = input("nhap goc ")
    controller.move_servo(id,angle)
    controller.read_response()
    
    
