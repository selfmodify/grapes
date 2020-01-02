# Implementation of custom AWS functions

import scripts


class AwsCustomFunctions():
    def set_env(self, env):
        self.config = env

    def _get_audio_video_lb_address(self, as_config_file, vs_config_file):
        # Get Audio Server LB details
        options = scripts.options.get_options()
        no_error_check = options.destroy() or options.dry_run()
        server_config = scripts.arg_parser.parse_config_from(as_config_file)
        elb_client = scripts.aws_client_elb.ElbClient(server_config)
        _, as_lb = elb_client.get_lb_details()
        if as_lb is None:
            if no_error_check:
                pass
            else:
                raise Exception('AudioServer LB not found')
        # Get Video Server LB details
        video_config = scripts.arg_parser.parse_config_from(vs_config_file)
        elb_client = scripts.aws_client_elb.ElbClient(video_config)
        _, vs_lb = elb_client.get_lb_details()
        if vs_lb is None:
            if no_error_check:
                pass
            else:
                raise Exception('VideoServer LB not found')
        as_port, _, _ = server_config.get_listener_info()
        vs_port, _, _ = video_config.get_listener_info()
        return as_lb, str(as_port), vs_lb, str(vs_port)

    def get_rtc_cmdline_params_port_range(self, as_config_file, vs_config_file):
        """
        Create the command line to be passed to RTC server.
        """
        as_lb, as_port, vs_lb, vs_port = self._get_audio_video_lb_address(
            as_config_file, vs_config_file)
        # Create the command line for RTC server
        s = '{0} -as={1}:{2} -vs={3}:{4} -min_port=30000 -max_port=65535'.format(
            self.config.get_cmdline_env_flag(), as_lb, as_port, vs_lb, vs_port)
        return s

    def get_rtc_cmdline_params(self, as_config_file, vs_config_file):
        """
        Create the command line to be passed to RTC server.
        This function does not add the -min_port and max_port param to the RTC command line
        """
        as_lb, as_port, vs_lb, vs_port = self._get_audio_video_lb_address(
            as_config_file, vs_config_file)
        # Create the command line for RTC server
        s = '{0} -as={1}:{2} -vs={3}:{4}'.format(
            self.config.get_cmdline_env_flag(), as_lb, as_port, vs_lb, vs_port)
        return s

    def get_mixdown_cmdline_params(self, as_config_file, vs_config_file):
        """
        Create the command line to be passed to Mixdown server.
        """
        as_lb, as_port, vs_lb, vs_port = self._get_audio_video_lb_address(
            as_config_file, vs_config_file)
        # Create the command line for RTC server
        s = '{0} -as={1}:{2} -vs={3}:{4}'.format(
            self.config.get_cmdline_env_flag(), as_lb,  as_port, vs_lb, vs_port)
        return s

    def generate_nginx_config_file(self,
                                   nginx_template_file,
                                   build_image_tag,
                                   region,
                                   s3bucket,
                                   as_config_file,
                                   rtc_config_file,
                                   mixdown_config_file,
                                   ui_config_file,
                                   upload_config_file):
        """
        Generate the NGINX conf file and upload it to S3
        """
        options = scripts.options.get_options()
        # Don't upload generated file if doing a dry run and deleting the service
        upload_to_s3 = not(options.destroy() or options.dry_run())
        config_file_list = [as_config_file, rtc_config_file,
                            mixdown_config_file, ui_config_file, upload_config_file]
        scripts.generate_nginx_conf.generate_nginx_config(
            nginx_template_file, build_image_tag, region, s3bucket, upload_to_s3, config_file_list)
        return 'Finished generating NGINX config file'

    def get_nginx_config_location(self, s3bucket, image_tag):
        return '{}/nginx-{}.conf'.format(s3bucket, image_tag)

    def get_custom_functions_map(self):
        # List of custom functions which can be used in the YAML file with the 'AwsCustomFunction' tag
        aws_fn_map = {
            'get_rtc_cmdline_params()': self.get_rtc_cmdline_params,
            'get_mixdown_cmdline_params()': self.get_mixdown_cmdline_params,
            'generate_nginx_config_file()': self.generate_nginx_config_file,
            'get_rtc_cmdline_params_port_range()': self.get_rtc_cmdline_params_port_range,
            'get_nginx_config_location()': self.get_nginx_config_location,
        }
        return aws_fn_map
